class PartialFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
