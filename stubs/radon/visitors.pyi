class Function:
    name: str
    lineno: int
    complexity: int

class Class:
    name: str
    lineno: int
    @property
    def complexity(self) -> int: ...
