"""Tests for available_moves tool (step 7 combat/exploration routing)."""

from straightjacket.engine.models import GameState, ProgressTrack, Resources


def _game(setting: str = "starforged", combat_position: str = "") -> GameState:
    g = GameState(player_name="Hero", setting_id=setting)
    g.resources = Resources(health=5, spirit=5, supply=5, momentum=2, max_momentum=10)
    g.world.combat_position = combat_position
    return g


class TestAvailableMoves:
    def test_no_combat_has_adventure_moves(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "adventure/face_danger" in move_keys
        assert "adventure/secure_an_advantage" in move_keys
        assert "adventure/gather_information" in move_keys

    def test_no_combat_has_enter_the_fray(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "combat/enter_the_fray" in move_keys
        assert "combat/battle" in move_keys

    def test_no_combat_excludes_combat_moves(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "combat/strike" not in move_keys
        assert "combat/clash" not in move_keys
        assert "combat/gain_ground" not in move_keys
        assert "combat/react_under_fire" not in move_keys

    def test_in_control_has_strike_and_gain_ground(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game(combat_position="in_control")
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "combat/strike" in move_keys
        assert "combat/gain_ground" in move_keys
        assert "combat/clash" not in move_keys
        assert "combat/react_under_fire" not in move_keys

    def test_bad_spot_has_clash_and_react(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game(combat_position="bad_spot")
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "combat/clash" in move_keys
        assert "combat/react_under_fire" in move_keys
        assert "combat/strike" not in move_keys
        assert "combat/gain_ground" not in move_keys

    def test_in_combat_excludes_enter_the_fray(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game(combat_position="in_control")
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "combat/enter_the_fray" not in move_keys

    def test_no_vow_excludes_fulfill(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "quest/fulfill_your_vow" not in move_keys
        assert "quest/swear_an_iron_vow" in move_keys

    def test_with_vow_includes_fulfill(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        game.progress_tracks.append(ProgressTrack(id="v1", name="Test Vow", track_type="vow", ticks=20))
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "quest/fulfill_your_vow" in move_keys

    def test_suffer_moves_excluded(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "suffer/endure_harm" not in move_keys
        assert "threshold/face_death" not in move_keys

    def test_recovery_moves_available(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "recover/heal" in move_keys
        assert "recover/resupply" in move_keys

    def test_engine_specific_moves_present(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "dialog" in move_keys
        assert "ask_the_oracle" in move_keys
        assert "world_shaping" in move_keys

    def test_combat_position_in_response(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game(combat_position="bad_spot")
        result = available_moves(game)
        assert result["combat_position"] == "bad_spot"

    def test_moves_include_stats(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        result = available_moves(game)
        fd = next(m for m in result["moves"] if m["move"] == "adventure/face_danger")
        assert set(fd["stats"]) == {"edge", "heart", "iron", "shadow", "wits"}

    def test_take_decisive_needs_combat_track(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game(combat_position="in_control")
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "combat/take_decisive_action" not in move_keys

        game.progress_tracks.append(ProgressTrack(id="c1", name="Fight", track_type="combat", ticks=12))
        result2 = available_moves(game)
        move_keys2 = {m["move"] for m in result2["moves"]}
        assert "combat/take_decisive_action" in move_keys2

    def test_classic_setting(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game(setting="classic")
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "adventure/face_danger" in move_keys
        assert "adventure/undertake_a_journey" in move_keys
        assert "relationship/compel" in move_keys
