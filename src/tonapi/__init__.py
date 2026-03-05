from __future__ import annotations


__all__ = ['TonAPI']

from typing import TYPE_CHECKING

from .methods import GetSeqno, GetWallet, SendMessage, GetTransactionByMessageHash
from .session import Session
import time


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

    async def wait_for_transfer(self, msg_hash: str, valid_until: int) -> Transaction:
        while True:
            request_time = time.time()
            try:
                return await self.get_transaction_by_msg_hash(msg_hash)
            except Exception:  # todo: log unexpected exceptions
                pass

            if request_time > valid_until:
                raise TimeoutError('Timeout waiting for transfer.')

    @property
    def session(self) -> Session:
        return self._session
