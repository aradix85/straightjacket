import pytest

from straightjacket.engine.models import ClockData
from straightjacket.engine.serialization import deserialize, serialize


def test_only_a_dataclass_is_serialized() -> None:
    with pytest.raises(TypeError, match="Expected dataclass instance, got dict"):
        serialize({"name": "not a dataclass"})


def test_only_a_dataclass_type_is_deserialized() -> None:
    with pytest.raises(TypeError, match="Expected dataclass type"):
        deserialize(dict, {})


def test_a_save_entry_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(TypeError, match="Expected dict, got list"):
        deserialize(ClockData, [])
