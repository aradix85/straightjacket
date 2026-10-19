from __future__ import annotations

import random
from dataclasses import dataclass

from .adventure_crafter import load_ac_data
from .config import crafter


@dataclass(frozen=True)
class CharacterTraits:
    special_trait: str
    identities: list[str]
    descriptors: list[str]


def _roll_twice_max(table: str, row_text: str, text_key: str) -> int:
    for entry in load_ac_data()[table]:
        if entry[text_key] == row_text:
            return int(entry["max"])
    raise LookupError(f"data/adventure_crafter.json {table} has no row {row_text!r}")


def lookup_character_special_trait(roll: int) -> str:
    data = load_ac_data()
    for entry in data["character_special_trait"]:
        if entry["min"] <= roll <= entry["max"]:
            return str(entry["trait"])
    raise LookupError(
        f"no character_special_trait entry covers roll={roll}; "
        f"data/adventure_crafter.json character_special_trait may be incomplete"
    )


def lookup_character_identity(roll: int) -> str:
    data = load_ac_data()
    for entry in data["character_identity"]:
        if entry["min"] <= roll <= entry["max"]:
            return str(entry["identity"])
    raise LookupError(
        f"no character_identity entry covers roll={roll}; "
        f"data/adventure_crafter.json character_identity may be incomplete"
    )


def lookup_character_descriptor(roll: int) -> str:
    data = load_ac_data()
    for entry in data["character_descriptors"]:
        if entry["min"] <= roll <= entry["max"]:
            return str(entry["descriptor"])
    raise LookupError(
        f"no character_descriptors entry covers roll={roll}; "
        f"data/adventure_crafter.json character_descriptors may be incomplete"
    )


def roll_character_traits(rng: random.Random) -> CharacterTraits:
    die = crafter().adventure_crafter_dice.table_die
    special_trait = lookup_character_special_trait(rng.randint(1, die))

    cfg = crafter().adventure_crafter
    identity_twice = _roll_twice_max("character_identity", cfg.identity_roll_twice_row, "identity")
    descriptor_twice = _roll_twice_max("character_descriptors", cfg.descriptor_roll_twice_row, "descriptor")

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
