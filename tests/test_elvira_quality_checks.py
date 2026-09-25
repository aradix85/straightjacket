def test_a_reworded_place_is_the_same_place() -> None:
    from tests.elvira.elvira_bot.quality_checks import _same_place

    assert _same_place("A narrow quay in a harbor; the harbor's name is unknown.", "A narrow quay in an unnamed harbor")
    assert _same_place("Cargo deck", "cargo deck ")


def test_a_different_place_is_a_move() -> None:
    from tests.elvira.elvira_bot.quality_checks import _same_place

    assert not _same_place("Saltmarrow docks", "Saltmarrow harbourmaster's office")
    assert not _same_place("Cargo deck of the Ashfall", "Bridge of the Ashfall")
