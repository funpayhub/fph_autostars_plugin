from __future__ import annotations

from typing import Any

from pydantic import Field, AliasChoices, computed_field, field_validator, field_serializer

from .base import FragmentMethod
from ..types import BuyStarsLink, BuyStarsResponse, RecipientResponse


class SearchStarsRecipient(FragmentMethod[RecipientResponse]):
    query: str
    quantity: int = Field(default=0, ge=0, le=1_000_000)
    __model_to_build__ = RecipientResponse

    @computed_field
    def method(self) -> str:
        return 'searchStarsRecipient'

    @field_serializer('quantity', mode='plain')
    def serialize_quantity(self, quantity: int) -> str:
        if not quantity:
            return ''
        return str(quantity)

    @field_validator('quantity', mode='before')
    @classmethod
    def validate_quantity(cls, v: Any) -> Any:
        return v or 0


class InitBuyStarsRequest(FragmentMethod[BuyStarsResponse]):
    recipient: str
    quantity: int = Field(ge=50, le=1_000_000)
    __model_to_build__ = BuyStarsResponse

    @computed_field
    def method(self) -> str:
        return 'initBuyStarsRequest'


class GetBuyStarsLink(FragmentMethod[BuyStarsLink]):
    request_id: str = Field(
        validation_alias=AliasChoices('id', 'request_id'),
        serialization_alias='id',
    )

    __model_to_build__ = BuyStarsLink

    @computed_field
    def method(self) -> str:
        return 'getBuyStarsLink'

    @computed_field
    def show_sender(self) -> str:
        return '0'

    @computed_field
    def transaction(self) -> str:
        return '1'
