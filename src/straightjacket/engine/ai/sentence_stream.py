import re
from collections.abc import Callable

from ..engine_loader import eng
from ..parser import clean_sentence
from .provider_base import decode_literal_unicode_escapes

_BOUNDARY = re.compile(r"[.!?\u2026]+[\"'\u201d\u2019)\]]*(?=\s)|\n\s*\n")


class SentenceStream:
    def __init__(self, on_sentence: Callable[[str], None]) -> None:
        self._on_sentence = on_sentence
        self._pending = ""
        self._first = True
        self.held = False
        self.failed = False
        self.emitted = 0

    @property
    def complete(self) -> bool:
        return self.emitted > 0 and not self.held and not self.failed

    def feed(self, delta: str) -> None:
        if self.held or self.failed:
            return
        self._pending = decode_literal_unicode_escapes(self._pending + delta)
        positions = [
            self._pending.find(marker) for marker in eng().parser.stream_hold_markers if marker in self._pending
        ]
        limit = min(positions) if positions else None
        end = self._boundary(limit)
        while end is not None:
            self._emit(self._pending[:end])
            self._pending = self._pending[end:]
            if limit is not None:
                limit -= end
            end = self._boundary(limit)
        if limit is not None:
            self.held = True

    def finish(self) -> None:
        if self.held or self.failed:
            return
        if self._pending.strip():
            self._emit(self._pending)
        self._pending = ""

    def fail(self) -> None:
        self.failed = True

    def _boundary(self, limit: int | None = None) -> int | None:
        abbreviations = eng().parser.stream_abbreviations
        for match in _BOUNDARY.finditer(self._pending):
            if limit is not None and match.end() > limit:
                return None
            head = self._pending[: match.end()].rstrip()
            if not any(head.endswith(abbreviation) for abbreviation in abbreviations):
                return match.end()
        return None

    def _emit(self, sentence: str) -> None:
        cleaned = clean_sentence(sentence, first=self._first)
        if cleaned:
            self._first = False
            self.emitted += 1
            self._on_sentence(cleaned)
