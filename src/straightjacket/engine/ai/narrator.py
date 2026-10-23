import json
from collections.abc import Sequence
from typing import Any

from ..config_loader import model_for_role, narration_language, sampling_params
from ..engine_loader import eng
from ..gamemaster.config import gm
from ..logging_util import log
from ..models import BrainResult, GameState
from ..parser import salvage_truncated_narration
from ..prompt_blocks import content_boundaries_block, get_narrator_system
from ..prompt_loader import get_prompt
from ..xml_utils import xa as _xa
from ..xml_utils import xe as _xe
from .provider_base import (
    AICallSpec,
    AIProvider,
    AIUnavailableError,
    NarrationSink,
    create_with_retry,
    stream_with_retry,
)
from .schemas import get_narrator_metadata_schema, get_opening_setup_schema


def call_narrator(
    provider: AIProvider,
    prompt: str,
    game: GameState,
    stream: NarrationSink | None = None,
) -> str:
    log(f"[Narrator] Calling narrator (prompt: {len(prompt)} chars)")
    messages = []
    for entry in game.narrative.narration_history[-gm().pacing.max_narration_history :]:
        messages.append({"role": "user", "content": entry.prompt_summary})
        messages.append({"role": "assistant", "content": entry.narration})
    messages.append({"role": "user", "content": prompt})

    system, cached_prefix = get_narrator_system(game)

    spec = AICallSpec(
        model=model_for_role("narrator"),
        system=system,
        messages=messages,
        json_schema=None,
        tools=None,
        log_role="narrator",
        cached_system_prefix=cached_prefix,
        **sampling_params("narrator"),
    )
    response = stream_with_retry(provider, spec, stream) if stream is not None else create_with_retry(provider, spec)
    raw = response.content
    if not raw.strip():
        raise AIUnavailableError("narrator: empty narration")

    if response.stop_reason == "truncated":
        log(f"[Narrator] WARNING: Response truncated at max_tokens ({len(raw)} chars)", level="warning")
        raw = salvage_truncated_narration(raw)

    log(f"[Narrator] Response ({len(raw)} chars): {raw[: eng().truncations.log_xlong]}...")
    return raw


def _no_opening_setup() -> dict[str, Any]:
    return {"npcs": [], "location": "", "scene_context": "", "memory_updates": [], "deceased_npcs": []}


def _no_narrator_metadata() -> dict[str, Any]:
    return {"new_npcs": [], "npc_renames": [], "npc_details": [], "deceased_npcs": [], "lore_npcs": []}


def call_opening_setup(provider: AIProvider, narration: str, game: GameState) -> dict[str, Any]:
    lang = narration_language()

    system = get_prompt("opening_setup_extractor", lang=lang)
    _defaults = eng().ai_text.narrator_defaults

    prompt = get_prompt(
        "opening_setup_request",
        narration=_xe(narration),
        player_name=_xe(game.player_name),
        genre=_xa(game.setting_genre),
        tone=_xa(game.setting_tone),
        description=_xe(game.setting_description),
        location=_xe(game.world.current_location or _defaults["unknown_location"]),
    )

    spec = AICallSpec(
        model=model_for_role("opening_setup"),
        system=system,
        messages=[{"role": "user", "content": prompt}],
        json_schema=get_opening_setup_schema(),
        tools=None,
        log_role="opening_setup",
        cached_system_prefix="",
        **sampling_params("opening_setup"),
    )
    try:
        data: dict[str, Any] = json.loads(create_with_retry(provider, spec).content)
        log(f"[OpeningSetup] Extracted: {len(data['npcs'])} NPCs, loc={data['location']}")
        return data
    except Exception as e:
        log(f"[OpeningSetup] Extraction failed: {e}", level="warning")
        return _no_opening_setup()


def call_narrator_metadata(
    provider: AIProvider,
    narration: str,
    game: GameState,
    brain: BrainResult,
    consequences: Sequence[str],
) -> dict[str, Any]:
    lang = narration_language()

    npc_refs = []
    npc_ids: list[str] = []
    for n in game.npcs:
        npc_ids.append(n.id)
        entry = get_prompt("metadata_npc_ref", id=n.id, npc=_xe(n.name))
        if n.aliases:
            entry += get_prompt("metadata_npc_aliases", aliases=_xe(", ".join(n.aliases)))
        if n.status == "deceased":
            entry += get_prompt("metadata_npc_deceased")
        elif n.status == "lore":
            entry += get_prompt("metadata_npc_lore")

        npc_loc = n.last_location
        if npc_loc:
            entry += get_prompt("metadata_npc_at", location=_xe(npc_loc))

        desc = n.description
        if desc:
            entry += get_prompt("metadata_npc_description", description=_xe(desc[: eng().truncations.prompt_xshort]))
        npc_refs.append(entry)

    parts = [get_prompt("metadata_context_move", move=brain.move)]
    if brain.stat != eng().ai_text.no_stat:
        parts.append(get_prompt("metadata_context_stat", stat=brain.stat))
    if brain.target_npc:
        parts.append(get_prompt("metadata_context_target", target=brain.target_npc))
    mechanical_ctx = "\n" + get_prompt(
        "metadata_engine_context",
        context=" | ".join(parts),
        consequences=get_prompt("metadata_context_consequences", consequences=_xe(", ".join(consequences)))
        if consequences
        else "",
    )

    system_base = get_prompt("narrator_metadata", lang=lang, dispositions="|".join(gm().enums.dispositions))

    cb = content_boundaries_block(game)
    system = f"{system_base}\n{cb}" if cb else system_base
    _defaults = eng().ai_text.narrator_defaults

    prompt = get_prompt(
        "narrator_metadata_request",
        narration=_xe(narration),
        player_name=_xe(game.player_name),
        known_npcs="\n".join(npc_refs) if npc_refs else _defaults["no_npcs"],
        location=_xe(game.world.current_location or _defaults["unknown_location"]),
        time=game.world.time_of_day or _defaults["unknown_time"],
        engine_context=mechanical_ctx,
    )

    spec = AICallSpec(
        model=model_for_role("narrator_metadata"),
        system=system,
        messages=[{"role": "user", "content": prompt}],
        json_schema=get_narrator_metadata_schema(npc_ids),
        tools=None,
        log_role="narrator_metadata",
        cached_system_prefix="",
        **sampling_params("narrator_metadata"),
    )
    try:
        metadata: dict[str, Any] = json.loads(create_with_retry(provider, spec).content)
        if not npc_ids and (metadata["npc_renames"] or metadata["npc_details"]):
            raise ValueError("the metadata renames or details an NPC, but no NPC is known")
        log(
            f"[Metadata] Extracted: "
            f"{len(metadata['new_npcs'])} new NPCs, "
            f"{len(metadata['npc_renames'])} renames, "
            f"{len(metadata['deceased_npcs'])} deceased, "
            f"{len(metadata['lore_npcs'])} lore"
        )
        return metadata
    except Exception as e:
        log(f"[Metadata] Extraction failed: {e}", level="warning")
        return _no_narrator_metadata()
