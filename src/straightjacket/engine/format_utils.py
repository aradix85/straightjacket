"""Shared utility: partial-format dict.

Used by prompt_loader and strings_loader. Zero internal dependencies
(safe to import during bootstrap, before the engine is loaded).
"""


class PartialFormatDict(dict):
    """Dict that returns '{key}' for missing keys, allowing partial formatting."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
