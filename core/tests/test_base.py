import pytest
from pydantic import Field, ValidationError

from jca_core.schema.base import FrozenModel


class Sample(FrozenModel):
    plain: int
    renamed: int = Field(alias="class")


def test_fields_cannot_be_reassigned():
    sample = Sample(plain=1, renamed=2)
    with pytest.raises(ValidationError):
        sample.plain = 5


def test_serialises_with_the_alias():
    assert Sample(plain=1, renamed=2).model_dump() == {"plain": 1, "class": 2}


def test_accepts_the_field_name_and_the_alias():
    assert Sample(plain=1, renamed=2) == Sample.model_validate({"plain": 1, "class": 2})


def test_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Sample.model_validate({"plain": 1, "class": 2, "extra": 3})
