import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from straightjacket.engine.ai.provider_base import (
    AICallSpec,
    AIProvider,
    AIUnavailableError,
    NarrationSink,
    create_with_retry,
    stream_with_retry,
)
from straightjacket.engine.ai.schemas import get_narrator_metadata_schema, get_opening_setup_schema
from straightjacket.engine.config_loader import model_for_role, narration_language, sampling_params
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.logging_util import log
from straightjacket.engine.models import BrainResult, GameState, NpcData
from straightjacket.engine.parser import salvage_truncated_narration
from straightjacket.engine.prompt_blocks import content_boundaries_block, get_narrator_system
from straightjacket.engine.prompt_loader import get_prompt
from straightjacket.engine.xml_utils import xa as _xa
from straightjacket.engine.xml_utils import xe as _xe

if TYPE_CHECKING:
    from straightjacket.engine.ai.provider_base import Message


def call_narrator(
    provider: AIProvider,
    prompt: str,
    game: GameState,
    stream: NarrationSink | None = None,
) -> str:
    log(f"[Narrator] Calling narrator (prompt: {len(prompt)} chars)")
    messages: list[Message] = []
    for entry in game.narrative.narration_history[-gm().pacing.max_narration_history :]:
        messages.extend(
            ({"role": "user", "content": entry.prompt_summary}, {"role": "assistant", "content": entry.narration})
        )
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
        sampling=sampling_params("narrator"),
    )
    response = stream_with_retry(provider, spec, stream) if stream is not None else create_with_retry(provider, spec)
    raw = response.content
    if not raw.strip():
        msg = "narrator: empty narration"
        raise AIUnavailableError(msg)

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
    defaults = eng().ai_text.narrator_defaults

    prompt = get_prompt(
        "opening_setup_request",
        narration=_xe(narration),
        player_name=_xe(game.player_name),
        genre=_xa(game.setting_genre),
        tone=_xa(game.setting_tone),
        description=_xe(game.setting_description),
        location=_xe(game.world.current_location or defaults["unknown_location"]),
    )

    spec = AICallSpec(
        model=model_for_role("opening_setup"),
        system=system,
        messages=[{"role": "user", "content": prompt}],
        json_schema=get_opening_setup_schema(),
        tools=None,
        log_role="opening_setup",
        cached_system_prefix="",
        sampling=sampling_params("opening_setup"),
    )
    try:
        data: dict[str, Any] = json.loads(create_with_retry(provider, spec).content)
        summary = f"{len(data['npcs'])} NPCs, loc={data['location']}"
    except Exception as e:
        log(f"[OpeningSetup] Extraction failed: {e}", level="warning")
        return _no_opening_setup()
    log(f"[OpeningSetup] Extracted: {summary}")
    return data


def _metadata_npc_ref(npc: NpcData) -> str:
    entry = get_prompt("metadata_npc_ref", id=npc.id, npc=_xe(npc.name))
    if npc.aliases:
        entry += get_prompt("metadata_npc_aliases", aliases=_xe(", ".join(npc.aliases)))
    if npc.status == "deceased":
        entry += get_prompt("metadata_npc_deceased")
    elif npc.status == "lore":
        entry += get_prompt("metadata_npc_lore")
    if npc.last_location:
        entry += get_prompt("metadata_npc_at", location=_xe(npc.last_location))
    if npc.description:
        description = npc.description[: eng().truncations.prompt_xshort]
        entry += get_prompt("metadata_npc_description", description=_xe(description))
    return entry


def _metadata_engine_context(brain: BrainResult, consequences: Sequence[str]) -> str:
    parts = [get_prompt("metadata_context_move", move=brain.move)]
    if brain.stat != eng().ai_text.no_stat:
        parts.append(get_prompt("metadata_context_stat", stat=brain.stat))
    if brain.target_npc:
        parts.append(get_prompt("metadata_context_target", target=brain.target_npc))
    return "\n" + get_prompt(
        "metadata_engine_context",
        context=" | ".join(parts),
        consequences=get_prompt("metadata_context_consequences", consequences=_xe(", ".join(consequences)))
        if consequences
        else "",
    )


def _metadata_request(game: GameState, narration: str, engine_context: str) -> str:
    npc_refs = [_metadata_npc_ref(n) for n in game.npcs]
    defaults = eng().ai_text.narrator_defaults
    return get_prompt(
        "narrator_metadata_request",
        narration=_xe(narration),
        player_name=_xe(game.player_name),
        known_npcs="\n".join(npc_refs) if npc_refs else defaults["no_npcs"],
        location=_xe(game.world.current_location or defaults["unknown_location"]),
        time=game.world.time_of_day or defaults["unknown_time"],
        engine_context=engine_context,
    )


def call_narrator_metadata(
    provider: AIProvider,
    narration: str,
    game: GameState,
    brain: BrainResult,
    consequences: Sequence[str],
) -> dict[str, Any]:
    npc_ids = [n.id for n in game.npcs]
    system_base = get_prompt(
        "narrator_metadata", lang=narration_language(), dispositions="|".join(gm().enums.dispositions)
    )
    cb = content_boundaries_block(game)
    system = f"{system_base}\n{cb}" if cb else system_base
    prompt = _metadata_request(game, narration, _metadata_engine_context(brain, consequences))

    spec = AICallSpec(
        model=model_for_role("narrator_metadata"),
        system=system,
        messages=[{"role": "user", "content": prompt}],
        json_schema=get_narrator_metadata_schema(npc_ids),
        tools=None,
        log_role="narrator_metadata",
        cached_system_prefix="",
        sampling=sampling_params("narrator_metadata"),
    )
    try:
        metadata = _checked_metadata(create_with_retry(provider, spec).content, npc_ids)
        summary = (
            f"{len(metadata['new_npcs'])} new NPCs, "
            f"{len(metadata['npc_renames'])} renames, "
            f"{len(metadata['deceased_npcs'])} deceased, "
            f"{len(metadata['lore_npcs'])} lore"
        )
    except Exception as e:
        log(f"[Metadata] Extraction failed: {e}", level="warning")
        return _no_narrator_metadata()
    log(f"[Metadata] Extracted: {summary}")
    return metadata


def _checked_metadata(content: str, npc_ids: list[str]) -> dict[str, Any]:
    metadata: dict[str, Any] = json.loads(content)
    if not npc_ids and (metadata["npc_renames"] or metadata["npc_details"]):
        msg = "the metadata renames or details an NPC, but no NPC is known"
        raise ValueError(msg)
    return metadata
