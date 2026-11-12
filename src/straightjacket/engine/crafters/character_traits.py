from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from straightjacket.engine.crafters.adventure_crafter import load_ac_data
from straightjacket.engine.crafters.config import crafter

if TYPE_CHECKING:
    import random
    from collections.abc import Iterable


@dataclass(frozen=True)
class CharacterTraits:
    special_trait: str
    identities: list[str]
    descriptors: list[str]


def _roll_twice_max(table: str, rows: Iterable[tuple[str, int]], row_text: str) -> int:
    for text, highest in rows:
        if text == row_text:
            return highest
    msg = f"data/adventure_crafter.json {table} has no row {row_text!r}"
    raise LookupError(msg)


def lookup_character_special_trait(roll: int) -> str:
    for entry in load_ac_data().character_special_trait:
        if entry.min <= roll <= entry.max:
            return entry.trait
    msg = (
        f"no character_special_trait entry covers roll={roll}; "
        f"data/adventure_crafter.json character_special_trait may be incomplete"
    )
    raise LookupError(msg)


def lookup_character_identity(roll: int) -> str:
    for entry in load_ac_data().character_identity:
        if entry.min <= roll <= entry.max:
            return entry.identity
    msg = (
        f"no character_identity entry covers roll={roll}; "
        f"data/adventure_crafter.json character_identity may be incomplete"
    )
    raise LookupError(msg)


def lookup_character_descriptor(roll: int) -> str:
    for entry in load_ac_data().character_descriptors:
        if entry.min <= roll <= entry.max:
            return entry.descriptor
    msg = (
        f"no character_descriptors entry covers roll={roll}; "
        f"data/adventure_crafter.json character_descriptors may be incomplete"
    )
    raise LookupError(msg)


def roll_character_traits(rng: random.Random) -> CharacterTraits:
    die = crafter().adventure_crafter_dice.table_die
    special_trait = lookup_character_special_trait(rng.randint(1, die))

    cfg = crafter().adventure_crafter
    data = load_ac_data()
    identity_twice = _roll_twice_max(
        "character_identity", ((row.identity, row.max) for row in data.character_identity), cfg.identity_roll_twice_row
    )
    descriptor_twice = _roll_twice_max(
        "character_descriptors",
        ((row.descriptor, row.max) for row in data.character_descriptors),
        cfg.descriptor_roll_twice_row,
    )

    identity_roll = rng.randint(1, die)
    if identity_roll <= identity_twice:
        identities = [
            lookup_character_identity(rng.randint(identity_twice + 1, die)),
            lookup_character_identity(rng.randint(identity_twice + 1, die)),
        ]
    else:
        identities = [lookup_character_identity(identity_roll)]

    descriptor_roll = rng.randint(1, die)
    if descriptor_roll <= descriptor_twice:
        descriptors = [
            lookup_character_descriptor(rng.randint(descriptor_twice + 1, die)),
            lookup_character_descriptor(rng.randint(descriptor_twice + 1, die)),
        ]
    else:
        descriptors = [lookup_character_descriptor(descriptor_roll)]

    return CharacterTraits(
        special_trait=special_trait,
        identities=identities,
        descriptors=descriptors,
    )
