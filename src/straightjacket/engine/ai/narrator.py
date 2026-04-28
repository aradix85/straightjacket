import json
from collections.abc import Sequence

from ..config_loader import model_for_role, sampling_params
from ..engine_loader import eng
from ..logging_util import log
from ..models import BrainResult, EngineConfig, GameState
from ..parser import salvage_truncated_narration
from ..prompt_blocks import content_boundaries_block, get_narration_lang, get_narrator_system
from ..prompt_loader import get_prompt
from .provider_base import AICallSpec, AIProvider, create_with_retry
from .schemas import get_narrator_metadata_schema, get_opening_setup_schema


def call_narrator(
    provider: AIProvider,
    prompt: str,
    game: GameState,
    config: EngineConfig | None = None,
    system_suffix: str = "",
    skip_history: bool = False,
    extra_messages: Sequence[dict] = (),
) -> str:
    log(f"[Narrator] Calling narrator (prompt: {len(prompt)} chars{', skip_history' if skip_history else ''})")
    messages = []

    if not skip_history and game.narrative.narration_history:
        for entry in game.narrative.narration_history[-eng().pacing.max_narration_history :]:
            messages.append({"role": "user", "content": entry.prompt_summary})
            messages.append({"role": "assistant", "content": entry.narration})

    messages.append({"role": "user", "content": prompt})

    if extra_messages:
        messages.extend(extra_messages)

    system = get_narrator_system(config or EngineConfig(), game)
    if system_suffix:
        system = system + "\n" + system_suffix

    spec = AICallSpec(
        model=model_for_role("narrator"),
        system=system,
        messages=messages,
        log_role="narrator",
        **sampling_params("narrator"),
    )
    response = create_with_retry(provider, spec)
    raw = response.content
    stop = response.stop_reason

    if stop == "truncated":
        log(f"[Narrator] WARNING: Response truncated at max_tokens ({len(raw)} chars)", level="warning")
        raw = salvage_truncated_narration(raw)
    else:
        _prose = raw[: raw.find("<game_data>")] if "<game_data>" in raw else raw
        _stripped = _prose.rstrip()
        if _stripped and _stripped[-1] not in '.!?"\u201c\u201d\u00bb\u00ab\u2026)\u2013\u2014*':
            log(
                f"[Narrator] WARNING: Response appears truncated despite complete "
                f"({len(raw)} chars, ends with '{_stripped[-20:]}')",
                level="warning",
            )
            raw = salvage_truncated_narration(raw)

    log(f"[Narrator] Response ({len(raw)} chars): {raw[: eng().truncations.log_xlong]}...")
    if "<game_data>" in raw:
        log("[Narrator] Found <game_data> tag (opening/chapter scene)")
    return raw


def call_opening_setup(
    provider: AIProvider, narration: str, game: GameState, config: EngineConfig | None = None
) -> dict:
    lang = get_narration_lang(config or EngineConfig())

    system = get_prompt("opening_setup_extractor", lang=lang)
    _defaults = eng().ai_text.narrator_defaults

    prompt = f"""<narration>{narration}</narration>
<player_character>{game.player_name}</player_character>
<world genre="{game.setting_genre}" tone="{game.setting_tone}">{game.setting_description}</world>
<current_location>{game.world.current_location or _defaults["unknown_location"]}</current_location>
Extract all NPCs, clocks, location, scene context, time of day, and initial NPC memories from the opening narration above.
IMPORTANT: {game.player_name} is the PLAYER CHARACTER — do NOT include them as an NPC. NPCs are OTHER characters the player meets."""

    try:
        spec = AICallSpec(
            model=model_for_role("opening_setup"),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=get_opening_setup_schema(),
            log_role="narrator_retry",
            **sampling_params("opening_setup"),
        )
        response = create_with_retry(provider, spec)
        data = json.loads(response.content)
        log(
            f"[OpeningSetup] Extracted: {len(data['npcs'])} NPCs, "
            f"{len(data['clocks'])} clocks, "
            f"loc={data['location']}, time={data['time_of_day']}"
        )
        return data
    except Exception as e:
        log(f"[OpeningSetup] Extraction failed: {e}", level="warning")
        defaults = eng().ai_text.narrator_defaults
        return {
            "npcs": defaults["opening_setup_fallback_npcs"],
            "clocks": defaults["opening_setup_fallback_clocks"],
            "location": defaults["opening_setup_fallback_location"],
            "scene_context": defaults["opening_setup_fallback_scene_context"],
            "time_of_day": defaults["unknown_time"],
            "memory_updates": defaults["opening_setup_fallback_memory_updates"],
        }


def call_narrator_metadata(
    provider: AIProvider,
    narration: str,
    game: GameState,
    config: EngineConfig | None = None,
    brain: BrainResult | None = None,
    consequences: Sequence[str] = (),
) -> dict:
    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)

    npc_refs = []
    for n in game.npcs:
        if n.status not in ("active", "background", "deceased", "lore"):
            continue
        entry = f"{n.id}={n.name}"
        if n.aliases:
            entry += f" (aka {', '.join(n.aliases)})"
        if n.status == "deceased":
            entry += " [DECEASED]"
        elif n.status == "lore":
            entry += " [LORE]"

        npc_loc = n.last_location
        if npc_loc:
            entry += f" [at:{npc_loc}]"

        desc = n.description
        if desc:
            entry += f" — {desc[: eng().truncations.prompt_xshort]}"
        npc_refs.append(entry)

    mechanical_ctx = ""
    if brain:
        parts = [f"move:{brain.move}"]
        if brain.stat and brain.stat != "none":
            parts.append(f"stat:{brain.stat}")
        if brain.target_npc:
            parts.append(f"target:{brain.target_npc}")
        mechanical_ctx = f"\n<engine_context>{' | '.join(parts)}"
        if consequences:
            mechanical_ctx += f" | consequences: {', '.join(consequences)}"
        mechanical_ctx += "</engine_context>"

    system_base = get_prompt("narrator_metadata", lang=lang)

    cb = content_boundaries_block(game)
    system = f"{system_base}\n{cb}" if cb else system_base
    _defaults = eng().ai_text.narrator_defaults

    prompt = f"""<narration>{narration}</narration>
<player_character>{game.player_name}</player_character>
<known_npcs>{chr(10).join(npc_refs) if npc_refs else _defaults["no_npcs"]}</known_npcs>
<current_location>{game.world.current_location or _defaults["unknown_location"]}</current_location>
<current_time>{game.world.time_of_day or _defaults["unknown_time"]}</current_time>{mechanical_ctx}
Extract all metadata from the narration above. Remember: {game.player_name} is the PLAYER CHARACTER, not an NPC."""

    try:
        spec = AICallSpec(
            model=model_for_role("narrator_metadata"),
            system=system,
            messages=[{"role": "user", "content": prompt}],
            json_schema=get_narrator_metadata_schema(),
            log_role="metadata",
            **sampling_params("narrator_metadata"),
        )
        response = create_with_retry(provider, spec)
        metadata = json.loads(response.content)
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
        defaults = eng().ai_text.narrator_defaults
        return {
            "new_npcs": defaults["narrator_metadata_fallback_new_npcs"],
            "npc_renames": defaults["narrator_metadata_fallback_npc_renames"],
            "npc_details": defaults["narrator_metadata_fallback_npc_details"],
            "deceased_npcs": defaults["narrator_metadata_fallback_deceased_npcs"],
            "lore_npcs": defaults["narrator_metadata_fallback_lore_npcs"],
        }
