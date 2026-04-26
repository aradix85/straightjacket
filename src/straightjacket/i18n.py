from .strings_loader import get_string, get_strings_by_prefix


def t(key: str, **kwargs: str | int) -> str:
    return get_string(key, **kwargs)


def get_disposition_labels() -> dict[str, str]:
    return get_strings_by_prefix("disposition.")


def get_time_labels() -> dict[str, str]:
    return get_strings_by_prefix("time.")


def get_story_phase_labels() -> dict[str, str]:
    return get_strings_by_prefix("story.")
