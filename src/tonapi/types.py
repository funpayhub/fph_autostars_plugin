from __future__ import annotations


__all__ = [
    'TonAPIResponse',
    'Seqno',
    'Transaction',
    'Wallet',
]


from typing import Any

from pydantic import Field, BaseModel


class TonAPIResponse(BaseModel):
    model_config = {'extra': 'allow'}
    ...


class Seqno(TonAPIResponse):
    seqno: int


class Transaction(TonAPIResponse):
    hash: str
    lt: int
    success: bool
    in_msg: dict[str, Any]
    out_msgs: list[dict[str, Any]] = Field(default_factory=list)


class Wallet(TonAPIResponse):
    address: str
    is_wallet: bool
    balance: int
