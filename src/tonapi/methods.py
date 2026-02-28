from __future__ import annotations

__all__ = [
    'TonAPIMethod',
    'SendMessage',
    'GetSeqno',
    'GetWallet',
    'GetTransactionByMessageHash',
]


from typing import ClassVar, Self, Literal
from abc import ABC
from pydantic import BaseModel
from collections.abc import Callable

from .types import Seqno, Wallet, Transaction


class TonAPIMethod[ReturnT](BaseModel, ABC):
    model_config = {'extra': 'allow'}
    path: ClassVar[str | Callable[[Self], str]]
    method: ClassVar[Literal['GET', 'POST']]
    return_type: ClassVar[ReturnT] = None

    def get_path(self) -> str:
        return self.path(self) if callable(self.path) else self.path


class SendMessage(TonAPIMethod):
    path = '/v2/blockchain/message'
    method = 'POST'
    boc: str


def _get_seqno_path(method: GetSeqno) -> str:
    return f'/v2/wallet/{method.address}/seqno'


class GetSeqno(TonAPIMethod):
    address: str
    path = _get_seqno_path
    method = 'GET'
    return_type = Seqno


def _get_wallet_path(method: GetWallet) -> str:
    return f'/v2/wallet/{method.address}'


class GetWallet(TonAPIMethod):
    address: str
    path = _get_wallet_path
    method = 'GET'
    return_type = Wallet


def _get_transaction_by_message_hash_path(method: GetTransactionByMessageHash) -> str:
    return f'/v2/blockchain/messages/{method.message_hash}/transaction'


class GetTransactionByMessageHash(TonAPIMethod):
    message_hash: str
    path = _get_transaction_by_message_hash_path
    method = 'GET'
    return_type = Transaction

