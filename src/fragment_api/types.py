from __future__ import annotations


__all__ = [
    'FragmentResponse',
    'RecipientInfo',
    'RecipientResponse',
    'BuyStarsResponse',
    'TransactionMessage',
    'TransactionInfo',
    'BuyStarsLink',
]


import re
import base64
from typing import Any

from pydantic import Field, BaseModel, computed_field, field_validator, field_serializer


DIRTY_REF_RE = re.compile(rb'Ref#(.+)')
CLEAR_REF_RE = re.compile(rb'[^A-Za-z0-9:#]')


class FragmentResponse(BaseModel):
    model_config = {'extra': 'allow'}


class RecipientInfo(BaseModel):
    myself: bool
    recipient: str
    photo: str
    name: str


class RecipientResponse(FragmentResponse):
    found: RecipientInfo


class BuyStarsResponse(FragmentResponse):
    request_id: str = Field(alias='req_id')
    myself: bool
    to_bot: bool
    amount: float = Field(ge=0)

    @field_validator('amount', mode='before')
    @classmethod
    def convert_amount(cls, v: Any) -> str:
        if not isinstance(v, str):
            return v
        return v.replace(',', '')


class TransactionMessage(BaseModel):
    address: str
    amount: int = Field(ge=0)
    payload: str

    @field_validator('payload', mode='after')
    @classmethod
    def add_padding(cls, v: str) -> str:
        padding = len(v) % 4
        if padding:
            v += '=' * (4 - padding)
        return v

    @computed_field
    @property
    def decoded_payload(self) -> bytes:
        return base64.b64decode(self.payload)

    @computed_field
    @property
    def clear_payload(self) -> str:
        ref = DIRTY_REF_RE.search(self.decoded_payload)
        return CLEAR_REF_RE.sub(b'', ref.group()).decode()

    @field_serializer('decoded_payload')
    def serialize_decoded_payload(self, v: bytes):
        return ''.join(f'\\x{b:02x}' for b in v)


class TransactionInfo(BaseModel):
    valid_until: int = Field(alias='validUntil')
    from_: str = Field(alias='from')
    messages: list[TransactionMessage]


class BuyStarsLink(FragmentResponse):
    transaction: TransactionInfo
    confirm_method: str
    confirm_params: dict[str, Any]
