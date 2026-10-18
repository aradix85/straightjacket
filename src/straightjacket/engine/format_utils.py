def describe_by_threshold(value: int, descriptions: dict[int, str]) -> str:
    return descriptions[max(threshold for threshold in descriptions if threshold <= value)]
