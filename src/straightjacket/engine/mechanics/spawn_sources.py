from __future__ import annotations

RANDOM_EVENT_SOURCE_PREFIX = "random_event:"
AC_SOURCE_PREFIX = "ac:"
CLOCK_KEYED_SOURCE_PREFIX = "clock:"
SETUP_SOURCE = "setup"

EMERGENT_SOURCE_PREFIXES: tuple[str, ...] = (RANDOM_EVENT_SOURCE_PREFIX, AC_SOURCE_PREFIX)
