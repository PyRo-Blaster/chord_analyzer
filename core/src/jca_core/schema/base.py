"""Base class for every record in the system."""

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """An immutable record that fails fast on unknown fields."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )
