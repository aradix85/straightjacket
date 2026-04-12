"""Tests for step 10: track type lifecycle, combat sync, scene challenge routing."""

from straightjacket.engine.models import GameState, ProgressTrack, Resources, WorldState


def _game(setting: str = "starforged", combat_position: str = "") -> GameState:
    g = GameState(player_name="Hero", setting_id=setting)
    g.resources = Resources(health=5, spirit=5, supply=5, momentum=2, max_momentum=10)
    g.world = WorldState(current_location="Iron Hold", combat_position=combat_position)
    return g


# ── 10.1 Combat track ↔ combat_position sync ────────────────


class TestCombatTrackSync:
    def test_complete_combat_track_clears_position(self) -> None:
        from straightjacket.engine.game.turn import complete_track

        game = _game(combat_position="in_control")
        game.progress_tracks.append(ProgressTrack(id="c1", name="Fight", track_type="combat", ticks=20))
        complete_track(game, "c1", "completed")
        assert game.progress_tracks[0].status == "completed"
        assert game.world.combat_position == ""

    def test_fail_combat_track_clears_position(self) -> None:
        from straightjacket.engine.game.turn import complete_track

        game = _game(combat_position="bad_spot")
        game.progress_tracks.append(ProgressTrack(id="c1", name="Fight", track_type="combat", ticks=8))
        complete_track(game, "c1", "failed")
        assert game.progress_tracks[0].status == "failed"
        assert game.world.combat_position == ""

    def test_complete_vow_does_not_clear_position(self) -> None:
        from straightjacket.engine.game.turn import complete_track

        game = _game(combat_position="in_control")
        game.progress_tracks.append(ProgressTrack(id="v1", name="Vow", track_type="vow", ticks=40))
        complete_track(game, "v1", "completed")
        assert game.world.combat_position == "in_control"

    def test_sync_removes_orphaned_combat_track(self) -> None:
        from straightjacket.engine.game.turn import sync_combat_tracks

        game = _game(combat_position="")
        game.progress_tracks.append(ProgressTrack(id="c1", name="Fight", track_type="combat", ticks=12))
        sync_combat_tracks(game)
        assert game.progress_tracks[0].status == "failed"

    def test_sync_ignores_active_combat_when_position_set(self) -> None:
        from straightjacket.engine.game.turn import sync_combat_tracks

        game = _game(combat_position="in_control")
        game.progress_tracks.append(ProgressTrack(id="c1", name="Fight", track_type="combat", ticks=12))
        sync_combat_tracks(game)
        assert game.progress_tracks[0].status == "active"

    def test_sync_ignores_already_completed_combat_track(self) -> None:
        from straightjacket.engine.game.turn import sync_combat_tracks

        game = _game(combat_position="")
        game.progress_tracks.append(
            ProgressTrack(id="c1", name="Fight", track_type="combat", ticks=40, status="completed")
        )
        sync_combat_tracks(game)
        assert game.progress_tracks[0].status == "completed"

    def test_sync_does_not_touch_non_combat_tracks(self) -> None:
        from straightjacket.engine.game.turn import sync_combat_tracks

        game = _game(combat_position="")
        game.progress_tracks.append(ProgressTrack(id="v1", name="Vow", track_type="vow", ticks=12))
        sync_combat_tracks(game)
        assert game.progress_tracks[0].status == "active"


# ── 10.2 Scene challenge progress routing ────────────────────


class TestSceneChallengeRouting:
    def test_face_danger_marks_scene_challenge(self, load_engine: None) -> None:
        from straightjacket.engine.engine_loader import eng

        sc_moves = eng().get_raw("scene_challenge_progress_moves", [])
        assert "adventure/face_danger" in sc_moves
        assert "adventure/secure_an_advantage" in sc_moves

    def test_scene_challenge_progress_on_hit(self, load_engine: None) -> None:
        """Scene challenge track gets progress when adventure move succeeds."""
        game = _game()
        sc = ProgressTrack(id="sc1", name="Escape", track_type="scene_challenge", rank="dangerous")
        game.progress_tracks.append(sc)
        old_ticks = sc.ticks
        sc.mark_progress()
        assert sc.ticks > old_ticks


# ── 10.3 available_moves status filter ───────────────────────


class TestAvailableMovesStatusFilter:
    def test_completed_vow_excludes_fulfill(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        game.progress_tracks.append(
            ProgressTrack(id="v1", name="Old Vow", track_type="vow", ticks=40, status="completed")
        )
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "quest/fulfill_your_vow" not in move_keys

    def test_active_vow_includes_fulfill(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        game.progress_tracks.append(ProgressTrack(id="v1", name="Active Vow", track_type="vow", ticks=20))
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "quest/fulfill_your_vow" in move_keys

    def test_failed_combat_track_excludes_decisive(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game(combat_position="in_control")
        game.progress_tracks.append(
            ProgressTrack(id="c1", name="Fight", track_type="combat", ticks=20, status="failed")
        )
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "combat/take_decisive_action" not in move_keys

    def test_completed_expedition_excludes_finish(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        game.progress_tracks.append(
            ProgressTrack(id="e1", name="Journey", track_type="expedition", ticks=40, status="completed")
        )
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "exploration/finish_an_expedition" not in move_keys

    def test_completed_scene_challenge_excludes_moves(self, load_engine: None) -> None:
        from straightjacket.engine.tools.builtins import available_moves

        game = _game()
        game.progress_tracks.append(
            ProgressTrack(id="sc1", name="Escape", track_type="scene_challenge", ticks=40, status="completed")
        )
        result = available_moves(game)
        move_keys = {m["move"] for m in result["moves"]}
        assert "scene_challenge/finish_the_scene" not in move_keys


# ── 10.4 /tracks status command ──────────────────────────────


class TestTracksStatus:
    def test_no_tracks(self) -> None:
        from straightjacket.web.serializers import build_tracks_status

        game = _game()
        result = build_tracks_status(game)
        assert "no active" in result.lower() or "No active" in result

    def test_vow_track_shown(self) -> None:
        from straightjacket.web.serializers import build_tracks_status

        game = _game()
        game.progress_tracks.append(ProgressTrack(id="v1", name="Iron Vow", track_type="vow", ticks=20))
        result = build_tracks_status(game)
        assert "Iron Vow" in result

    def test_combat_track_shows_position(self) -> None:
        from straightjacket.web.serializers import build_tracks_status

        game = _game(combat_position="in_control")
        game.progress_tracks.append(ProgressTrack(id="c1", name="Fight", track_type="combat", ticks=12))
        result = build_tracks_status(game)
        assert "Fight" in result
        assert "in control" in result

    def test_completed_track_not_shown(self) -> None:
        from straightjacket.web.serializers import build_tracks_status

        game = _game()
        game.progress_tracks.append(
            ProgressTrack(id="v1", name="Done Vow", track_type="vow", ticks=40, status="completed")
        )
        result = build_tracks_status(game)
        assert "Done Vow" not in result
