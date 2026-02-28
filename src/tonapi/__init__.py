from __future__ import annotations

__all__ = ['TonAPI']

from typing import TYPE_CHECKING
from .session import Session
from .methods import GetSeqno, GetWallet, SendMessage, GetTransactionByMessageHash


if TYPE_CHECKING:
    from .types import Seqno, Wallet, Transaction


class TonAPI:
    def __init__(self):
        self._session = Session()

    async def get_seqno(self, address: str) -> Seqno:
        return await self.session.make_request(GetSeqno(address=address))

    async def get_wallet(self, address: str) -> Wallet:
        return await self.session.make_request(GetWallet(address=address))

    async def send_message(self, boc: str) -> bool:
        return await self.session.make_request(SendMessage(boc=boc))

    async def get_transaction_by_msg_hash(self, hash: str) -> Transaction:
        return await self.session.make_request(GetTransactionByMessageHash(message_hash=hash))

    @property
    def session(self) -> Session:
        return self._session