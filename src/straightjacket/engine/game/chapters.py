import copy
import re
from concurrent.futures import ThreadPoolExecutor

from ..ai.architect import call_chapter_summary, call_story_architect
from ..ai.metadata import process_deceased_npcs
from ..ai.narrator import call_narrator, call_opening_setup
from ..ai.provider_base import AIProvider
from ..db import sync as _db_sync
from ..db.connection import reset_db
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics import (
    choose_story_structure,
    record_scene_intensity,
)
from ..models import (
    ChapterSummary,
    DirectorGuidance,
    EngineConfig,
    GameState,
    NarrationEntry,
    NpcData,
    NpcEvolution,
    ProgressTrack,
    SceneLogEntry,
    StoryBlueprint,
    ThreadEntry,
    ThreatData,
)
from ..npc import (
    consolidate_memory,
    get_npc_bond,
    next_npc_id,
)
from ..parser import parse_narrator_response
from ..prompt_boundary import build_epilogue_prompt, build_new_chapter_prompt
from ..user_management import load_user_config, save_user_config

from .setup_common import apply_opening_setup


def generate_epilogue(
    provider: AIProvider, game: GameState, config: EngineConfig | None = None
) -> tuple[GameState, str]:
    log(
        f"[Epilogue] Generating epilogue for {game.player_name} (chapter {game.campaign.chapter_number}, scene {game.narrative.scene_count})"
    )

    raw = call_narrator(provider, build_epilogue_prompt(game), game, config)
    narration = parse_narrator_response(game, raw)

    narration = re.sub(
        r"^\s*#*\s*\*{0,3}\s*Epilog(?:ue)?\s*\*{0,3}\s*\n+",
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
    log(f"[Campaign] Starting chapter {game.campaign.chapter_number + 1} for {game.player_name}")

    chapter_summary = _close_previous_chapter(provider, game, config)
    _reset_chapter_mechanics(game)
    _restore_chapter_mechanics(game, chapter_summary)
    _prepare_npcs_for_new_chapter(game)

    threads = chapter_summary.unresolved_threads
    _chap = eng().chapter
    _defaults = eng().ai_text.narrator_defaults
    if threads:
        threads_text = "; ".join(threads[: _chap.scene_context_threads_max])
        game.world.current_scene_context = _defaults["new_chapter_threads_template"].format(threads=threads_text)
    else:
        game.world.current_scene_context = _defaults["new_chapter_blank"]

    returning_npcs = [copy.deepcopy(n) for n in game.npcs if n.status in ("active", "background", "deceased")]

    narration, setup_data = _generate_chapter_opening(provider, game, config, returning_npcs)

    _merge_returning_npcs(game, returning_npcs)

    if setup_data.get("deceased_npcs"):
        process_deceased_npcs(game, setup_data["deceased_npcs"])

    _record_chapter_opening(game, narration)

    if username and game.preferences.content_lines:
        user_cfg = load_user_config(username)
        user_cfg["content_lines"] = game.preferences.content_lines
        save_user_config(username, user_cfg)

    reset_db()
    _db_sync(game)

    return game, narration


def _close_previous_chapter(provider: AIProvider, game: GameState, config: EngineConfig | None) -> ChapterSummary:
    epilogue = game.campaign.epilogue_text or ""
    narrative = call_chapter_summary(provider, game, config, epilogue_text=epilogue)
    chapter_summary = ChapterSummary(
        chapter=game.campaign.chapter_number,
        title=narrative["title"],
        summary=narrative["summary"],
        unresolved_threads=list(narrative["unresolved_threads"]),
        character_growth=narrative["character_growth"],
        npc_evolutions=[NpcEvolution(**e) for e in narrative["npc_evolutions"]],
        thematic_question=narrative["thematic_question"],
        post_story_location=narrative["post_story_location"],
        scenes=game.narrative.scene_count,
        progress_tracks=[ProgressTrack.from_dict(p.to_dict()) for p in game.progress_tracks],
        threats=[ThreatData.from_dict(t.to_dict()) for t in game.threats],
        impacts=list(game.impacts),
        assets=list(game.assets),
        threads=[ThreadEntry.from_dict(th.to_dict()) for th in game.narrative.threads],
    )
    game.campaign.campaign_history.append(chapter_summary)

    post_loc = chapter_summary.post_story_location
    if post_loc:
        game.world.current_location = post_loc

    game.campaign.chapter_number += 1
    return chapter_summary


def _reset_chapter_mechanics(game: GameState) -> None:
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

    game.progress_tracks = []
    game.threats = []
    game.impacts = []
    game.assets = []
    game.narrative.threads = []


def _restore_chapter_mechanics(game: GameState, summary: ChapterSummary) -> None:
    game.progress_tracks = [ProgressTrack.from_dict(p.to_dict()) for p in summary.progress_tracks]
    game.threats = [ThreatData.from_dict(t.to_dict()) for t in summary.threats]
    game.impacts = list(summary.impacts)
    game.assets = list(summary.assets)
    game.narrative.threads = [ThreadEntry.from_dict(th.to_dict()) for th in summary.threads]


def _prepare_npcs_for_new_chapter(game: GameState) -> None:
    for npc in game.npcs:
        if npc.status == "deceased" or npc.status != "active":
            continue
        is_filler = (
            get_npc_bond(game, npc.id) <= eng().chapter.filler_bond_max
            and len(npc.memory) <= eng().chapter.filler_max
            and not npc.agenda.strip()
        )
        if is_filler:
            npc.status = "background"
            log(f"[Campaign] Retired NPC to background at chapter boundary: {npc.name} (low-engagement filler)")

    _chap_cfg = eng().chapter
    for npc in game.npcs:
        if npc.memory and len(npc.memory) > _chap_cfg.open_threads_max:
            scored = sorted(npc.memory, key=lambda m: (m.importance, m.scene), reverse=True)
            npc.memory = sorted(scored[: _chap_cfg.open_threads_max], key=lambda m: m.scene)
        consolidate_memory(npc)


def _generate_chapter_opening(
    provider: AIProvider, game: GameState, config: EngineConfig | None, returning_npcs: list[NpcData]
) -> tuple[str, dict]:
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

    _apply_blueprint(game, provider, blueprint)

    returning_ids = {n.id for n in returning_npcs}
    new_parser_npcs = [n for n in game.npcs if n.id not in returning_ids]
    setup_data = {}
    if not new_parser_npcs:
        setup_data = call_opening_setup(provider, narration, game, config)
        _apply_chapter_opening_setup(game, setup_data, returning_npcs)
    else:
        log(f"[Campaign] New NPCs already extracted by parser ({len(new_parser_npcs)}), skipping opening_setup call")

    return narration, setup_data


def _apply_blueprint(game: GameState, provider: AIProvider, blueprint: dict | None) -> None:
    if blueprint is not None:
        game.narrative.story_blueprint = StoryBlueprint.from_dict(blueprint)
    else:
        game.narrative.story_blueprint = None


def _merge_returning_npcs(game: GameState, returning_npcs: list[NpcData]) -> None:
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


def _record_chapter_opening(game: GameState, narration: str) -> None:
    record_scene_intensity(game, "action")
    game.narrative.narration_history.append(
        NarrationEntry(
            scene=1,
            prompt_summary=f"Chapter {game.campaign.chapter_number} opening: {game.player_name} in {game.world.current_location}",
            narration=narration,
        )
    )
    game.narrative.session_log.append(
        SceneLogEntry(
            scene=1,
            scene_type="expected",
            summary=f"Chapter {game.campaign.chapter_number} begins",
            result="opening",
        )
    )


def _apply_chapter_opening_setup(game: GameState, data: dict, returning_npcs: list[NpcData]) -> None:
    apply_opening_setup(game, data, returning_npcs=returning_npcs, clocks_mode="extend", label="ChapterSetup")
