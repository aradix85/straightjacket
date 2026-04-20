"""XML escaping helpers. Single source of truth for prompt safety."""

import html as _html


def xa(s: str) -> str:
    """Escape a string for safe use as an XML attribute value."""
    return _html.escape(str(s), quote=True)


def xe(s: str) -> str:
    """Escape a string for safe use as XML element content."""
    return _html.escape(str(s), quote=False)
