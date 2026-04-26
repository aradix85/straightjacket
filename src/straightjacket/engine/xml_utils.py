import html as _html


def xa(s: str) -> str:
    return _html.escape(str(s), quote=True)


def xe(s: str) -> str:
    return _html.escape(str(s), quote=False)
