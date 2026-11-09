import pytest

from straightjacket.engine.gamemaster.stance_gate import resolve_npc_stance
from straightjacket.engine.models import (
    GameState,
    NpcData,
)
from straightjacket.engine.prompt_dialog import build_dialog_prompt
from tests._helpers import (
    action_prompt,
    dialog_prompt_kwargs,
    docks_game,
    friendly_kira,
    make_brain_result,
    make_memory,
    make_npc,
    make_progress_track,
    weak_hit_prompt,
)


def _npc(disposition: str = "neutral") -> NpcData:
    return make_npc(
        id="npc_1",
        name="Kira",
        description="A wary trader",
        agenda="Protect her cargo",
        instinct="Counts exits before entering",
        disposition=disposition,
        memory=[make_memory(scene=1, event="Kira appeared at the docks", emotional_weight="neutral", importance=3)],
    )


def _game(npc: NpcData | None = None, bond: int = 0) -> GameState:
    return docks_game(npc, scene=3, bond=bond)


def test_hostile_low_combat() -> None:
    npc = _npc("hostile")
    game = _game(npc, bond=0)
    stance = resolve_npc_stance(game, npc, "combat", miss=False, hit=False)
    assert stance.stance == "aggressive"
    assert "quarter" in stance.constraint.lower() or "hesitation" in stance.constraint.lower()


def test_distrustful_low_gather() -> None:
    npc = _npc("distrustful")
    game = _game(npc, bond=1)
    stance = resolve_npc_stance(game, npc, "gather_information", miss=False, hit=False)
    assert stance.stance == "evasive"
    assert "silent" in stance.constraint.lower()


def test_friendly_mid_social() -> None:
    npc = _npc("friendly")
    game = _game(npc, bond=2)
    stance = resolve_npc_stance(game, npc, "social", miss=False, hit=False)
    assert stance.stance == "confiding"


def test_loyal_high_other() -> None:
    npc = _npc("loyal")
    game = _game(npc, bond=4)
    stance = resolve_npc_stance(game, npc, "other", miss=False, hit=False)
    assert stance.stance == "ride_or_die"


def test_neutral_low_other() -> None:
    npc = _npc("neutral")
    game = _game(npc, bond=0)
    stance = resolve_npc_stance(game, npc, "other", miss=False, hit=False)
    assert stance.stance == "indifferent"


def test_bond_range_mid() -> None:
    npc = _npc("neutral")
    game = _game(npc, bond=2)
    stance = resolve_npc_stance(game, npc, "social", miss=False, hit=False)
    assert stance.stance == "engaged"


def test_bond_range_high() -> None:
    npc = _npc("neutral")
    game = _game(npc, bond=4)
    stance = resolve_npc_stance(game, npc, "social", miss=False, hit=False)
    assert stance.stance == "open"


def test_unknown_move_category_raises() -> None:
    npc = _npc("neutral")
    game = _game(npc, bond=1)
    with pytest.raises(KeyError):
        resolve_npc_stance(game, npc, "unknown_category", miss=False, hit=False)


def test_stance_constraint_not_empty() -> None:
    for disp in ("hostile", "distrustful", "neutral", "friendly", "loyal"):
        for bond in (0, 2, 4):
            for cat in ("combat", "social", "gather_information", "other"):
                npc = _npc(disp)
                game = _game(npc, bond=bond)
                stance = resolve_npc_stance(game, npc, cat, miss=False, hit=False)
                assert stance.constraint, f"Empty constraint for {disp}/{bond}/{cat}"
                assert stance.stance, f"Empty stance for {disp}/{bond}/{cat}"


def test_stance_in_target_npc_block() -> None:
    npc = _npc("distrustful")
    game = _game(npc, bond=1)
    brain = make_brain_result(
        move="adventure/gather_information", stat="wits", target_npc="npc_1", player_intent="ask about the cargo"
    )
    prompt = weak_hit_prompt(game, brain, "I ask about the cargo")
    assert 'stance="evasive"' in prompt
    assert "constraint=" in prompt

    assert 'disposition="distrustful"' not in prompt
    assert 'bond="1/4"' not in prompt


def _compel_a_hostile_npc(result: str) -> str:
    npc = _npc("hostile")
    game = _game(npc, bond=0)
    brain = make_brain_result(move="adventure/compel", stat="iron", target_npc="npc_1", player_intent="make them talk")
    return action_prompt(game, brain, result, player_words="Talk.")


@pytest.mark.parametrize(
    ("result", "stance"), [("STRONG_HIT", "yielding"), ("WEAK_HIT", "yielding"), ("MISS", "withholding")]
)
def test_a_hostile_target_gives_way_to_a_hit(result: str, stance: str) -> None:
    prompt = _compel_a_hostile_npc(result)
    assert f'stance="{stance}"' in prompt
    assert "Refuses to engage" not in prompt


@pytest.mark.parametrize(
    ("category", "bond", "without_a_roll", "on_a_hit"),
    [
        ("social", 0, "hostile", "yielding"),
        ("gather_information", 0, "stonewalling", "yielding"),
        ("social", 2, "confrontational", "yielding"),
        ("gather_information", 2, "misleading", "yielding"),
        ("social", 4, "bitter", "bitter"),
        ("combat", 0, "aggressive", "aggressive"),
    ],
)
def test_only_a_refusing_stance_gives_way_to_a_hit(
    category: str, bond: int, without_a_roll: str, on_a_hit: str
) -> None:
    npc = _npc("hostile")
    game = _game(npc, bond=bond)
    assert resolve_npc_stance(game, npc, category, miss=False, hit=False).stance == without_a_roll
    assert resolve_npc_stance(game, npc, category, miss=False, hit=True).stance == on_a_hit


def test_stance_in_activated_npc_block() -> None:
    npc1 = friendly_kira(agenda="Trade", instinct="Cautious")
    npc2 = make_npc(id="npc_2", name="Rowan", disposition="hostile", agenda="Fight", instinct="Reckless")
    game = _game()
    game.npcs = [npc1, npc2]
    game.progress_tracks.append(
        make_progress_track(id="connection_npc_1", name="Kira", track_type="connection", rank="dangerous", ticks=8)
    )
    brain = make_brain_result(move="adventure/face_danger", stat="edge", target_npc="npc_1", player_intent="dodge")
    prompt = action_prompt(
        game,
        brain,
        "STRONG_HIT",
        consequence_sentences=["The tide shifts."],
        player_words="dodge",
        activated_npcs=[npc1, npc2],
    )

    assert "stance=" in prompt
    assert 'disposition="hostile"' not in prompt


def test_dialog_prompt_uses_social_stance() -> None:
    npc = _npc("distrustful")
    game = _game(npc, bond=1)
    brain = make_brain_result(move="dialog", dialog_only=True, target_npc="npc_1", player_intent="ask a question")
    prompt = build_dialog_prompt(
        game,
        brain,
        **dialog_prompt_kwargs(player_words="What happened last night?", activated_npcs=[npc]),
    )
    assert 'stance="guarded"' in prompt
