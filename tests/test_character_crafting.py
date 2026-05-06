from __future__ import annotations

import random

import pytest

from straightjacket.engine.mechanics.adventure_crafter import (
    CharacterTraits,
    lookup_character_descriptor,
    lookup_character_identity,
    lookup_character_special_trait,
    roll_character_traits,
)


_SPECIAL_TRAIT_BOUNDARIES = [
    (1, "individual"),
    (50, "individual"),
    (51, "organization"),
    (57, "organization"),
    (58, "object"),
    (64, "object"),
    (65, "connected_to_plotline"),
    (71, "connected_to_plotline"),
    (72, "not_connected_to_plotline"),
    (78, "not_connected_to_plotline"),
    (79, "assists_plotline"),
    (85, "assists_plotline"),
    (86, "hinders_plotline"),
    (92, "hinders_plotline"),
    (93, "connected_to_existing_character"),
    (100, "connected_to_existing_character"),
]


@pytest.mark.parametrize("roll,expected", _SPECIAL_TRAIT_BOUNDARIES)
def test_lookup_character_special_trait_boundaries(roll: int, expected: str) -> None:
    assert lookup_character_special_trait(roll) == expected


def test_lookup_character_special_trait_full_coverage_1_to_100() -> None:
    for roll in range(1, 101):
        result = lookup_character_special_trait(roll)
        assert isinstance(result, str)
        assert result != ""


@pytest.mark.parametrize("roll", [0, -1, 101, 200])
def test_lookup_character_special_trait_out_of_range_raises(roll: int) -> None:
    with pytest.raises(ValueError, match="outside 1..100"):
        lookup_character_special_trait(roll)


def test_lookup_character_identity_flag_range_returns_flag_text() -> None:
    for roll in (1, 17, 33):
        assert lookup_character_identity(roll) == "Roll for two Identities"


def test_lookup_character_identity_full_coverage_1_to_100() -> None:
    for roll in range(1, 101):
        result = lookup_character_identity(roll)
        assert isinstance(result, str)
        assert result != ""


def test_lookup_character_identity_99_filled() -> None:
    assert lookup_character_identity(99) == "Spy"


def test_lookup_character_identity_boundary_examples() -> None:
    assert lookup_character_identity(34) == "Warrior"
    assert lookup_character_identity(50) == "Mediator"
    assert lookup_character_identity(100) == "Exotic"


@pytest.mark.parametrize("roll", [0, -1, 101, 9999])
def test_lookup_character_identity_out_of_range_raises(roll: int) -> None:
    with pytest.raises(ValueError, match="outside 1..100"):
        lookup_character_identity(roll)


def test_lookup_character_descriptor_flag_range_returns_flag_text() -> None:
    for roll in (1, 11, 21):
        assert lookup_character_descriptor(roll) == "Roll for two Descriptors"


def test_lookup_character_descriptor_full_coverage_1_to_100() -> None:
    for roll in range(1, 101):
        result = lookup_character_descriptor(roll)
        assert isinstance(result, str)
        assert result != ""


def test_lookup_character_descriptor_boundary_examples() -> None:
    assert lookup_character_descriptor(22) == "Ugly"
    assert lookup_character_descriptor(100) == "Heroic"


@pytest.mark.parametrize("roll", [0, -1, 101])
def test_lookup_character_descriptor_out_of_range_raises(roll: int) -> None:
    with pytest.raises(ValueError, match="outside 1..100"):
        lookup_character_descriptor(roll)


def test_roll_character_traits_returns_struct_with_required_fields() -> None:
    rng = random.Random(42)
    traits = roll_character_traits(rng)
    assert isinstance(traits, CharacterTraits)
    assert isinstance(traits.special_trait, str) and traits.special_trait != ""
    assert isinstance(traits.identities, list)
    assert isinstance(traits.descriptors, list)


def test_roll_character_traits_identities_length_1_or_2() -> None:
    for seed in range(50):
        rng = random.Random(seed)
        traits = roll_character_traits(rng)
        assert len(traits.identities) in (1, 2)
        for ident in traits.identities:
            assert ident != "Roll for two Identities"


def test_roll_character_traits_descriptors_length_1_or_2() -> None:
    for seed in range(50):
        rng = random.Random(seed)
        traits = roll_character_traits(rng)
        assert len(traits.descriptors) in (1, 2)
        for desc in traits.descriptors:
            assert desc != "Roll for two Descriptors"


def test_roll_character_traits_dual_identity_uses_non_flag_range() -> None:
    class StubRNG:
        def __init__(self, sequence: list[int]) -> None:
            self._seq = list(sequence)

        def randint(self, a: int, b: int) -> int:
            return self._seq.pop(0)

    rng = StubRNG([100, 5, 50, 75, 100])
    traits = roll_character_traits(rng)  # type: ignore[arg-type]
    assert traits.special_trait == "connected_to_existing_character"
    assert len(traits.identities) == 2
    assert traits.identities[0] == "Mediator"
    assert traits.identities[1] == "Villain"
    assert len(traits.descriptors) == 1
    assert traits.descriptors[0] == "Heroic"


def test_roll_character_traits_two_descriptors_uses_non_flag_range() -> None:
    class StubRNG:
        def __init__(self, sequence: list[int]) -> None:
            self._seq = list(sequence)

        def randint(self, a: int, b: int) -> int:
            return self._seq.pop(0)

    rng = StubRNG([1, 100, 15, 22, 100])
    traits = roll_character_traits(rng)  # type: ignore[arg-type]
    assert traits.special_trait == "individual"
    assert len(traits.identities) == 1
    assert traits.identities[0] == "Exotic"
    assert len(traits.descriptors) == 2
    assert traits.descriptors[0] == "Ugly"
    assert traits.descriptors[1] == "Heroic"


def test_roll_character_traits_single_identity_path() -> None:
    class StubRNG:
        def __init__(self, sequence: list[int]) -> None:
            self._seq = list(sequence)

        def randint(self, a: int, b: int) -> int:
            return self._seq.pop(0)

    rng = StubRNG([50, 99, 50])
    traits = roll_character_traits(rng)  # type: ignore[arg-type]
    assert traits.identities == ["Spy"]
    assert traits.descriptors == ["Colorful"]


def test_roll_character_traits_deterministic_with_fixed_seed() -> None:
    rng_a = random.Random(12345)
    rng_b = random.Random(12345)
    traits_a = roll_character_traits(rng_a)
    traits_b = roll_character_traits(rng_b)
    assert traits_a == traits_b


def test_character_traits_is_frozen() -> None:
    traits = CharacterTraits(special_trait="individual", identities=["Hero"], descriptors=["Strong"])
    with pytest.raises((AttributeError, Exception)):
        traits.special_trait = "object"  # type: ignore[misc]
