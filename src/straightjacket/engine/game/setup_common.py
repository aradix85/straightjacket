import random
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from straightjacket.engine.ai.blueprint_voicing import call_blueprint_voicing
from straightjacket.engine.ai.narrator import call_narrator, call_opening_setup
from straightjacket.engine.ai.provider_base import AIProvider
from straightjacket.engine.crafters.blueprint import assemble_blueprint_seed_from_ac, materialize_blueprint
from straightjacket.engine.gamemaster.npc.lifecycle import new_npc
from straightjacket.engine.gamemaster.npc.matching import (
    apply_name_sanitization,
    find_npc,
    fuzzy_match_existing_npc,
    named_in,
    next_npc_id,
)
from straightjacket.engine.gamemaster.npc.memory import score_importance
from straightjacket.engine.gamemaster.pacing import record_scene_intensity
from straightjacket.engine.gamemaster.random_events import drop_scenes_of_departed_npcs
from straightjacket.engine.gamemaster.world import update_location
from straightjacket.engine.logging_util import log
from straightjacket.engine.models import (
    GameState,
    MemoryEntry,
    NarrationEntry,
    OpeningMemory,
    OpeningNpc,
    OpeningSetup,
    SceneLogEntry,
)
from straightjacket.engine.parser import parse_narrator_response


def register_extracted_npcs(game: GameState, extracted: list[OpeningNpc]) -> None:
    player_lower = game.player_name.lower().strip()

    for nd in extracted:
        name = nd.name.lower().strip()
        if not name or name == player_lower:
            continue
        known = find_npc(game, nd.name) or fuzzy_match_existing_npc(game, nd.name)[0]
        if known is not None:
            log(f"[NPC] Extracted '{nd.name}' is the known '{known.name}', not a new NPC")
            continue
        npc = new_npc(
            npc_id=next_npc_id(game),
            name=nd.name,
            disposition=nd.disposition,
            status="active",
            name_rolled=False,
            description=nd.description,
            agenda=nd.agenda,
            instinct=nd.instinct,
            secrets=list(nd.secrets),
            aliases=[],
            last_location=game.world.current_location,
            introduced=False,
        )
        apply_name_sanitization(npc)
        game.npcs.append(npc)

    game.npcs = [n for n in game.npcs if n.name.lower().strip() != player_lower]
    drop_scenes_of_departed_npcs(game)


def seed_opening_memories(game: GameState, memory_updates: list[OpeningMemory]) -> None:
    for mu in memory_updates:
        target = find_npc(game, mu.npc_name) or next((n for n in game.npcs if named_in(n, mu.npc_name)), None)
        if not target:
            continue
        imp = score_importance(mu.emotional_weight, mu.event)
        target.memory.append(
            MemoryEntry(
                scene=game.narrative.scene_count,
                event=mu.event,
                emotional_weight=mu.emotional_weight,
                importance=imp,
                type="observation",
                tone="",
                tone_key="",
                about_npc=None,
            )
        )
        target.importance_accumulator += imp


def apply_opening_setup(game: GameState, setup: OpeningSetup, *, label: str) -> None:
    if setup.npcs:
        known_ids = {n.id for n in game.npcs}
        register_extracted_npcs(game, setup.npcs)
        new_names = [n.name for n in game.npcs if n.id not in known_ids]
        log(f"[{label}] Registered {len(new_names)} new NPCs: {new_names}")

    seed_opening_memories(game, setup.memory_updates)

    if setup.location:
        update_location(game, setup.location)

    if setup.scene_context:
        game.world.current_scene_context = setup.scene_context


def generate_opening(
    provider: AIProvider, game: GameState, build_prompt: Callable[[GameState], str], *, label: str
) -> tuple[str, OpeningSetup]:
    seed = assemble_blueprint_seed_from_ac(random.Random(), game)
    log(f"[{label}] Blueprint seed assembled: themes={seed.themes}")
    narrator_prompt = build_prompt(game)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_narrator = pool.submit(call_narrator, provider, narrator_prompt, game)
        fut_voicing = pool.submit(call_blueprint_voicing, provider, game, seed)
        raw = fut_narrator.result()
        voicing = fut_voicing.result()

    narration = parse_narrator_response(game, raw)
    game.narrative.story_blueprint = None if voicing is None else materialize_blueprint(seed, voicing)

    setup = call_opening_setup(provider, narration, game)
    apply_opening_setup(game, setup, label=label)
    return narration, setup


def record_opening(game: GameState, narration: str, history_summary: str, log_summary: str) -> None:
    record_scene_intensity(game, "action")
    game.narrative.narration_history.append(
        NarrationEntry(scene=1, prompt_summary=history_summary, narration=narration)
    )
    game.narrative.session_log.append(
        SceneLogEntry(
            scene=1,
            scene_type="expected",
            summary=log_summary,
            move="",
            result="opening",
            position="",
            effect="",
            rich_summary="",
            oracle_answer="",
        )
    )
