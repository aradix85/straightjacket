from __future__ import annotations

import random

from .config import gm


def choose_story_structure(tone: str) -> str:
    probability = gm().story.kishotenketsu_probability[tone]
    return "kishotenketsu" if random.random() < probability else "3act"
