from straightjacket.engine.ids import next_id


def test_the_first_id_of_a_prefix_is_one() -> None:
    assert next_id("ks_", []) == "ks_1"


def test_the_next_id_follows_the_highest_number_and_never_reuses_a_gap() -> None:
    assert next_id("npc_", ["npc_1", "npc_4", "npc_2"]) == "npc_5"


def test_ids_of_another_prefix_or_without_a_number_do_not_count() -> None:
    assert next_id("ac_char_", ["ac_plot_7", "ac_char_x", "ac_char_2"]) == "ac_char_3"
