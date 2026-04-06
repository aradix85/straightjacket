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


def generate_epilogue(provider: AIProvider, game: GameState,
                      config: EngineConfig | None = None) -> tuple[GameState, str]:
    """Generate an epilogue for the completed story. Returns (game, epilogue_text)."""
    log(f"[Epilogue] Generating epilogue for {game.player_name} (chapter {game.campaign.chapter_number}, scene {game.narrative.scene_count})")

    raw = call_narrator(provider, build_epilogue_prompt(game), game, config)

    # Clean the response — strip any metadata that might leak through
    narration = raw
    # Remove known metadata XML tags (paired)
    narration = re.sub(r'<(?:game_data|new_npcs|memory_updates|scene_context)>.*?</(?:game_data|new_npcs|memory_updates|scene_context)>', '', narration, flags=re.DOTALL)
    # Remove known self-closing/unpaired metadata tags only (not ALL XML — narrator
    # may use tags like <sigh> or <emphasis> as stylistic prose elements)
    narration = re.sub(r'</?(?:game_data|new_npcs|memory_updates|scene_context|task|scene|world|character|situation|conflict|possible_endings|session_log|npc|returning_npc|campaign_history|chapter|story_arc|story_ending|momentum_burn)[^>]*>', '', narration)
    # Remove lines that start with [ or { (trailing JSON metadata)
    # Use MULTILINE so each line is checked independently (DOTALL would eat everything)
    narration = re.sub(r'^\s*[\[{].*$', '', narration, flags=re.MULTILINE)
    # Strip redundant "Epilog/Epilogue" heading the narrator likes to add
    # (the scene marker already labels this section visually)
    narration = re.sub(
        r'^\s*#*\s*\*{0,3}\s*(?:Epilog(?:ue)?|Épilogue|Epílogo|Epilogo)\s*\*{0,3}\s*\n+',
        '', narration, count=1, flags=re.IGNORECASE
    )
    narration = narration.strip()
    # Normalize em-dash and en-dash to spaced hyphen
    narration = re.sub(r'\s*[—–]\s*', ' - ', narration)

    if not narration:
        narration = "(The narrator pauses, then offers a quiet reflection on the journey...)"

    game.campaign.epilogue_shown = True
    game.campaign.epilogue_text = narration
    log(f"[Epilogue] Generated ({len(narration)} chars)")
    return game, narration

def start_new_chapter(provider: AIProvider, game: GameState,
                      config: EngineConfig | None = None,
                      username: str = "") -> tuple[GameState, str]:
    """Start a new chapter: keep character/world/NPCs, reset mechanics, new story arc."""
    log(f"[Campaign] Starting chapter {game.campaign.chapter_number + 1} for {game.player_name}")

    # Generate chapter summary before resetting — include epilogue if available
    epilogue = game.campaign.epilogue_text or ""
    chapter_summary = call_chapter_summary(provider, game, config, epilogue_text=epilogue)
    game.campaign.campaign_history.append(chapter_summary)

    # Update location from epilogue conclusion (v0.9.68: prevents new chapter
    # opening at mid-action location instead of post-epilogue location)
    post_loc = chapter_summary.post_story_location
    if post_loc:
        game.world.current_location = post_loc

    # Advance chapter
    game.campaign.chapter_number += 1

    # Reset mechanics
    game.resources.health = eng().resources.health_start
    game.resources.spirit = eng().resources.spirit_start
    game.resources.supply = eng().resources.supply_start
    game.resources.momentum = eng().momentum.start
    game.narrative.scene_count = 1
    game.world.chaos_factor = eng().chaos.start
    game.crisis_mode = False
    game.game_over = False
    game.campaign.epilogue_shown = False
    game.campaign.epilogue_dismissed = False
    game.campaign.epilogue_text = ""  # Clear — consumed by chapter summary above
    game.world.clocks = []
    game.narrative.session_log = []
    game.narrative.narration_history = []
    game.narrative.scene_intensity_history = []
    game.narrative.story_blueprint = None  # Cleared; new blueprint generated after opening scene
    game.world.time_of_day = ""      # Reset -- new chapter, new time context
    game.world.location_history = []  # Reset -- new chapter, fresh location tracking
    from ..models import DirectorGuidance
    game.narrative.director_guidance = DirectorGuidance()  # Reset -- old pacing/guidance shouldn't carry over

    # Retire dead or irrelevant NPCs to background before new chapter
    for npc in game.npcs:
        # Deceased NPCs stay deceased — skip them entirely
        if npc.status == "deceased":
            continue
        if npc.status != "active":
            continue
        # Low-engagement NPCs: no bond, minimal memories, no agenda (filler NPCs)
        is_filler = (npc.bond == 0
                     and len(npc.memory) <= 1
                     and not npc.agenda.strip())
        if is_filler:
            npc.status = "background"
            log(f"[Campaign] Retired NPC to background at chapter boundary: "
                f"{npc.name} (low-engagement filler)")

    # Keep NPCs but consolidate memories (keep significant ones across chapters)
    for npc in game.npcs:
        if npc.memory and len(npc.memory) > 5:
            # Keep the 5 most impactful memories (by importance score, then recency)
            scored = sorted(
                npc.memory,
                key=lambda m: (m.importance, m.scene),
                reverse=True
            )
            npc.memory = sorted(scored[:5], key=lambda m: m.scene)
        # Run full consolidation to ensure memory limits are respected
        consolidate_memory(npc)

    # Update situation context for new chapter
    threads = chapter_summary.unresolved_threads
    if threads:
        game.world.current_scene_context = f"New chapter. Open threads: {'; '.join(threads[:3])}"
    else:
        game.world.current_scene_context = "A new chapter begins."

    # Save returning NPCs before parse replaces them (active + background + deceased)
    returning_npcs: list[NpcData] = [copy.deepcopy(n) for n in game.npcs
                      if n.status in ("active", "background", "deceased")]

    # Choose story structure for new chapter (needed before parallel calls)
    structure = choose_story_structure(game.setting_tone)

    # Prepare narrator prompt before parallel calls
    chapter_prompt = build_new_chapter_prompt(game)

    # --- Parallel execution: Narrator + Story Architect simultaneously ---
    # The architect gets the pre-parse state (returning NPCs, current context),
    # which is actually ideal for campaign continuity. New chapter NPCs from the
    # narrator's game_data are a bonus; the blueprint is about story arcs, not NPC details.
    # We use copy.copy(game) so parse_narrator_response's mutations (replacing game.npcs,
    # updating location/context) don't race with the architect's reads.
    from concurrent.futures import ThreadPoolExecutor

    architect_game = copy.copy(game)  # Shallow copy — frozen view for architect

    def _run_narrator():
        return call_narrator(provider, chapter_prompt, game, config)

    def _run_architect():
        return call_story_architect(provider, architect_game, structure_type=structure, config=config)

    raw = None
    blueprint = None
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_narrator = pool.submit(_run_narrator)
        fut_architect = pool.submit(_run_architect)
        raw = fut_narrator.result()
        blueprint = fut_architect.result()

    narration = parse_narrator_response(game, raw)

    # Constraint validation on chapter opening (up to 2 retries)
    from ..ai.validator import validate_and_retry, validate_architect
    narration, val_report = validate_and_retry(
        provider, narration, chapter_prompt, "opening", game, config=config)

    # Validate architect blueprint for genre fidelity
    from ..datasworn.settings import active_package
    _pkg = active_package(game)
    _gc = None
    if _pkg:
        _g = _pkg.genre_constraints
        _gc = {"forbidden_terms": _g.forbidden_terms, "forbidden_concepts": _g.forbidden_concepts, "genre_test": _g.genre_test}
    from ..models import StoryBlueprint
    if blueprint is not None:
        blueprint = validate_architect(provider, blueprint, game.setting_genre, game.setting_tone, genre_constraints=_gc)
        game.narrative.story_blueprint = StoryBlueprint.from_dict(blueprint)
    else:
        game.narrative.story_blueprint = None

    # --- Two-call pattern: extract opening setup from prose ---
    # Count how many NEW NPCs the parser found (not returning ones)
    returning_ids = {n.id for n in returning_npcs}
    new_parser_npcs = [n for n in game.npcs if n.id not in returning_ids]
    setup_data = {}
    if not new_parser_npcs:
        setup_data = call_opening_setup(provider, narration, game, config)
        _apply_chapter_opening_setup(game, setup_data, returning_npcs)
    else:
        log(f"[Campaign] New NPCs already extracted by parser ({len(new_parser_npcs)}), "
            f"skipping opening_setup call")

    # Merge: re-add returning NPCs that weren't re-introduced by the extractor.
    # NOTE: Do NOT check by old ID here. _process_game_data() / _apply_chapter_opening_setup()
    # reassigned IDs starting from npc_1 into the now-empty game.npcs, so old IDs from the
    # previous chapter will collide with freshly assigned ones. Name-based dedup is the only
    # correct check after an ID reassignment.
    new_npc_names = {n.name.lower().strip() for n in game.npcs}
    id_remap = {}  # old_id -> new_id; needed to fix about_npc references below
    for old_npc in returning_npcs:
        # Skip if extractor already created an NPC with this name
        if old_npc.name.lower().strip() in new_npc_names:
            continue
        # Assign a fresh ID to avoid collisions with extractor-assigned IDs
        old_id = old_npc.id
        fresh_id, _ = next_npc_id(game)
        id_remap[old_id] = fresh_id
        old_npc.id = fresh_id
        old_npc.introduced = True  # Player knows them from previous chapter
        game.npcs.append(old_npc)
        new_npc_names.add(old_npc.name.lower().strip())

    # Fix stale about_npc references across all NPC memories.
    # Returning NPCs carry memories from the previous chapter whose about_npc values
    # reference old IDs. After the ID reassignment above those IDs no longer exist
    # (or worse, point to different NPCs), breaking the NPC-to-NPC memory relevance
    # boost in retrieve_memories(). Rewrite every stale reference in one pass.
    if id_remap:
        for npc in game.npcs:
            for mem in npc.memory:
                if mem.about_npc and mem.about_npc in id_remap:
                    mem.about_npc = id_remap[mem.about_npc]

    # Seed location_history with the new chapter's starting location
    if game.world.current_location and not game.world.location_history:
        game.world.location_history.append(game.world.current_location)

    # Deceased NPCs in the chapter opening. Processed after the merge loop so
    # returning NPCs are already in game.npcs and reachable by name.
    # No scene_present_ids guard — everything in the opening is witnessed.
    if setup_data.get("deceased_npcs"):
        from ..ai.metadata import process_deceased_npcs
        process_deceased_npcs(game, setup_data["deceased_npcs"])

    # Record opening
    record_scene_intensity(game, "action")
    game.narrative.narration_history.append(NarrationEntry(
        prompt_summary=f"Chapter {game.campaign.chapter_number} opening: {game.player_name} in {game.world.current_location}",
        narration=narration,
    ))
    game.narrative.session_log.append(SceneLogEntry(
        scene=1, summary=f"Chapter {game.campaign.chapter_number} begins",
        result="opening", validator=val_report,
    ))

    # Persist content_lines to user config (auto-fill for next game)
    if username and game.preferences.content_lines:
        user_cfg = load_user_config(username)
        user_cfg["content_lines"] = game.preferences.content_lines
        save_user_config(username, user_cfg)

    # Note: UI layer handles save_game()
    return game, narration

def _apply_chapter_opening_setup(game: GameState, data: dict,
                                  returning_npcs: list[NpcData]):
    """Apply opening setup extraction to a new chapter."""
    from .setup_common import apply_world_setup, register_extracted_npcs, seed_opening_memories

    returning_names = {n.name.lower().strip() for n in returning_npcs}

    # Determine starting ID from existing + returning NPCs
    import re as _re
    max_num = 0
    for n in game.npcs + returning_npcs:
        m = _re.match(r'npc_(\d+)', str(n.id))
        if m:
            max_num = max(max_num, int(m.group(1)))

    if data.get("npcs"):
        register_extracted_npcs(
            game, data["npcs"],
            skip_names=returning_names,
            start_id=max_num,
            label="ChapterSetup",
        )
        returning_ids = {r.id for r in returning_npcs}
        new_names = [n.name for n in game.npcs
                     if n.id not in returning_ids]
        log(f"[ChapterSetup] Registered {len(new_names)} new NPCs: {new_names}")

    if data.get("memory_updates"):
        seed_opening_memories(game, data["memory_updates"], label="chapter_setup")

    apply_world_setup(game, data, clocks_mode="extend")
