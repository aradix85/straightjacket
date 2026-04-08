#!/usr/bin/env python3
"""Chapter management: epilogue generation, new chapter orchestration."""

import copy
import re

from ..ai.architect import call_chapter_summary, call_story_architect
from ..ai.narrator import call_narrator, call_opening_setup
from ..ai.provider_base import AIProvider
from ..engine_loader import eng
from ..logging_util import load_user_config, log, save_user_config
from ..mechanics import (
    choose_story_structure,
    record_scene_intensity,
)
from ..models import (
    DirectorGuidance,
    EngineConfig,
    GameState,
    NarrationEntry,
    NpcData,
    SceneLogEntry,
)
from ..npc import (
    consolidate_memory,
    next_npc_id,
)
from ..parser import parse_narrator_response
from ..prompt_builders import build_epilogue_prompt, build_new_chapter_prompt


def generate_epilogue(
    provider: AIProvider, game: GameState, config: EngineConfig | None = None
) -> tuple[GameState, str]:
    """Generate an epilogue for the completed story. Returns (game, epilogue_text)."""
    log(
        f"[Epilogue] Generating epilogue for {game.player_name} (chapter {game.campaign.chapter_number}, scene {game.narrative.scene_count})"
    )

    raw = call_narrator(provider, build_epilogue_prompt(game), game, config)

    narration = raw
    narration = re.sub(
        r"<(?:game_data|new_npcs|memory_updates|scene_context)>.*?</(?:game_data|new_npcs|memory_updates|scene_context)>",
        "",
        narration,
        flags=re.DOTALL,
    )
    narration = re.sub(
        r"</?(?:game_data|new_npcs|memory_updates|scene_context|task|scene|world|character|situation|conflict|possible_endings|session_log|npc|returning_npc|campaign_history|chapter|story_arc|story_ending|momentum_burn)[^>]*>",
        "",
        narration,
    )
    narration = re.sub(r"^\s*[\[{].*$", "", narration, flags=re.MULTILINE)
    narration = re.sub(
        r"^\s*#*\s*\*{0,3}\s*(?:Epilog(?:ue)?|Épilogue|Epílogo|Epilogo)\s*\*{0,3}\s*\n+",
        "",
        narration,
        count=1,
        flags=re.IGNORECASE,
    )
    narration = narration.strip()

    if not narration:
        narration = "(The narrator pauses, then offers a quiet reflection on the journey...)"

    game.campaign.epilogue_shown = True
    game.campaign.epilogue_text = narration
    log(f"[Epilogue] Generated ({len(narration)} chars)")
    return game, narration


def start_new_chapter(
    provider: AIProvider, game: GameState, config: EngineConfig | None = None, username: str = ""
) -> tuple[GameState, str]:
    """Start a new chapter: keep character/world/NPCs, reset mechanics, new story arc."""
    log(f"[Campaign] Starting chapter {game.campaign.chapter_number + 1} for {game.player_name}")

    chapter_summary = _close_previous_chapter(provider, game, config)
    _reset_chapter_mechanics(game)
    _prepare_npcs_for_new_chapter(game)

    threads = chapter_summary.unresolved_threads
    if threads:
        game.world.current_scene_context = f"New chapter. Open threads: {'; '.join(threads[:3])}"
    else:
        game.world.current_scene_context = "A new chapter begins."

    returning_npcs = [copy.deepcopy(n) for n in game.npcs if n.status in ("active", "background", "deceased")]

    narration, val_report, setup_data = _generate_chapter_opening(provider, game, config, returning_npcs)

    _merge_returning_npcs(game, returning_npcs)

    if setup_data.get("deceased_npcs"):
        from ..ai.metadata import process_deceased_npcs

        process_deceased_npcs(game, setup_data["deceased_npcs"])

    _record_chapter_opening(game, narration, val_report)

    if username and game.preferences.content_lines:
        user_cfg = load_user_config(username)
        user_cfg["content_lines"] = game.preferences.content_lines
        save_user_config(username, user_cfg)

    return game, narration


# ── Phase 1: Close previous chapter ─────────────────────────


def _close_previous_chapter(provider, game, config):
    """Generate chapter summary and advance chapter number."""
    epilogue = game.campaign.epilogue_text or ""
    chapter_summary = call_chapter_summary(provider, game, config, epilogue_text=epilogue)
    game.campaign.campaign_history.append(chapter_summary)

    post_loc = chapter_summary.post_story_location
    if post_loc:
        game.world.current_location = post_loc

    game.campaign.chapter_number += 1
    return chapter_summary


# ── Phase 2: Reset mechanics ────────────────────────────────


def _reset_chapter_mechanics(game: GameState) -> None:
    """Reset all per-chapter mechanical state to starting values."""
    _e = eng()
    game.resources.health = _e.resources.health_start
    game.resources.spirit = _e.resources.spirit_start
    game.resources.supply = _e.resources.supply_start
    game.resources.momentum = _e.momentum.start
    game.narrative.scene_count = 1
    game.world.chaos_factor = _e.chaos.start
    game.crisis_mode = False
    game.game_over = False
    game.campaign.epilogue_shown = False
    game.campaign.epilogue_dismissed = False
    game.campaign.epilogue_text = ""
    game.world.clocks = []
    game.narrative.session_log = []
    game.narrative.narration_history = []
    game.narrative.scene_intensity_history = []
    game.narrative.story_blueprint = None
    game.world.time_of_day = ""
    game.world.location_history = []
    game.narrative.director_guidance = DirectorGuidance()


# ── Phase 3: NPC pruning and consolidation ───────────────────


def _prepare_npcs_for_new_chapter(game: GameState) -> None:
    """Retire filler NPCs to background and consolidate memories."""
    for npc in game.npcs:
        if npc.status == "deceased" or npc.status != "active":
            continue
        is_filler = npc.bond == 0 and len(npc.memory) <= 1 and not npc.agenda.strip()
        if is_filler:
            npc.status = "background"
            log(f"[Campaign] Retired NPC to background at chapter boundary: {npc.name} (low-engagement filler)")

    for npc in game.npcs:
        if npc.memory and len(npc.memory) > 5:
            scored = sorted(npc.memory, key=lambda m: (m.importance, m.scene), reverse=True)
            npc.memory = sorted(scored[:5], key=lambda m: m.scene)
        consolidate_memory(npc)


# ── Phase 4: Generate opening ────────────────────────────────


def _generate_chapter_opening(provider, game, config, returning_npcs):
    """Run narrator + architect in parallel, validate, extract setup.
    Returns (narration, val_report, setup_data)."""
    from concurrent.futures import ThreadPoolExecutor

    structure = choose_story_structure(game.setting_tone)
    chapter_prompt = build_new_chapter_prompt(game)
    architect_game = copy.copy(game)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_narrator = pool.submit(call_narrator, provider, chapter_prompt, game, config)
        fut_architect = pool.submit(
            call_story_architect, provider, architect_game, structure_type=structure, config=config
        )
        raw = fut_narrator.result()
        blueprint = fut_architect.result()

    narration = parse_narrator_response(game, raw)

    from ..ai.validator import validate_and_retry

    narration, val_report = validate_and_retry(provider, narration, chapter_prompt, "opening", game, config=config)

    _apply_blueprint(game, provider, blueprint)

    returning_ids = {n.id for n in returning_npcs}
    new_parser_npcs = [n for n in game.npcs if n.id not in returning_ids]
    setup_data = {}
    if not new_parser_npcs:
        setup_data = call_opening_setup(provider, narration, game, config)
        _apply_chapter_opening_setup(game, setup_data, returning_npcs)
    else:
        log(f"[Campaign] New NPCs already extracted by parser ({len(new_parser_npcs)}), skipping opening_setup call")

    return narration, val_report, setup_data


def _apply_blueprint(game, provider, blueprint):
    """Validate and apply story architect blueprint."""
    from ..ai.validator import validate_architect
    from ..datasworn.settings import active_package
    from ..models import StoryBlueprint

    gc = None
    pkg = active_package(game)
    if pkg:
        g = pkg.genre_constraints
        gc = {
            "forbidden_terms": g.forbidden_terms,
            "forbidden_concepts": g.forbidden_concepts,
            "genre_test": g.genre_test,
        }

    if blueprint is not None:
        blueprint = validate_architect(provider, blueprint, game.setting_genre, game.setting_tone, genre_constraints=gc)
        game.narrative.story_blueprint = StoryBlueprint.from_dict(blueprint)
    else:
        game.narrative.story_blueprint = None


# ── Phase 5: Merge returning NPCs ───────────────────────────


def _merge_returning_npcs(game: GameState, returning_npcs: list[NpcData]) -> None:
    """Re-add returning NPCs not re-introduced by the extractor, fix ID references."""
    new_npc_names = {n.name.lower().strip() for n in game.npcs}
    id_remap: dict[str, str] = {}

    for old_npc in returning_npcs:
        if old_npc.name.lower().strip() in new_npc_names:
            continue
        old_id = old_npc.id
        fresh_id, _ = next_npc_id(game)
        id_remap[old_id] = fresh_id
        old_npc.id = fresh_id
        old_npc.introduced = True
        game.npcs.append(old_npc)
        new_npc_names.add(old_npc.name.lower().strip())

    if id_remap:
        for npc in game.npcs:
            for mem in npc.memory:
                if mem.about_npc and mem.about_npc in id_remap:
                    mem.about_npc = id_remap[mem.about_npc]

    if game.world.current_location and not game.world.location_history:
        game.world.location_history.append(game.world.current_location)


# ── Record opening ───────────────────────────────────────────


def _record_chapter_opening(game: GameState, narration: str, val_report: dict) -> None:
    """Record opening scene in narration history and session log."""
    record_scene_intensity(game, "action")
    game.narrative.narration_history.append(
        NarrationEntry(
            prompt_summary=f"Chapter {game.campaign.chapter_number} opening: {game.player_name} in {game.world.current_location}",
            narration=narration,
        )
    )
    game.narrative.session_log.append(
        SceneLogEntry(
            scene=1,
            summary=f"Chapter {game.campaign.chapter_number} begins",
            result="opening",
            validator=val_report,
        )
    )


# ── Chapter opening setup ────────────────────────────────────


def _apply_chapter_opening_setup(game: GameState, data: dict, returning_npcs: list[NpcData]):
    """Apply opening setup extraction to a new chapter."""
    from .setup_common import apply_world_setup, register_extracted_npcs, seed_opening_memories

    returning_names = {n.name.lower().strip() for n in returning_npcs}

    max_num = 0
    for n in game.npcs + returning_npcs:
        m = re.match(r"npc_(\d+)", str(n.id))
        if m:
            max_num = max(max_num, int(m.group(1)))

    if data.get("npcs"):
        register_extracted_npcs(
            game,
            data["npcs"],
            skip_names=returning_names,
            start_id=max_num,
            label="ChapterSetup",
        )
        returning_ids = {r.id for r in returning_npcs}
        new_names = [n.name for n in game.npcs if n.id not in returning_ids]
        log(f"[ChapterSetup] Registered {len(new_names)} new NPCs: {new_names}")

    if data.get("memory_updates"):
        seed_opening_memories(game, data["memory_updates"], label="chapter_setup")

    apply_world_setup(game, data, clocks_mode="extend")
