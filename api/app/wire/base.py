"""The base for every request and response model: Python names snake_case, JSON speaks camelCase."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """`populate_by_name` keeps a snake_case body acceptable, for hand-written requests and tests."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
