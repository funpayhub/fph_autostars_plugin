from __future__ import annotations

import time
import asyncio
from typing import TYPE_CHECKING, Self
from dataclasses import dataclass

from pytoniq import Cell, Address, WalletV5R1
from pytoniq_core import StateInit, MessageAny, WalletMessage
from pytoniq_core.crypto.keys import mnemonic_is_valid, mnemonic_to_private_key
from autostars.src.tonapi.types import Wallet as TonAPIWallet
from pytoniq.contract.wallets.wallet_v5 import WALLET_V5_R1_CODE


if TYPE_CHECKING:
    from autostars.src.autostars_provider import AutostarsProvider


@dataclass
class Transfer:
    address: str
    amount: int
    payload: str = ''
    valid_until: int | None = None

    def __post_init__(self) -> None:
        if self.valid_until is None:
            self.valid_until = int(time.time() + 60)


class OfflineV5R1Wallet:
    def __init__(self, mnemonic: str) -> None:
        if not mnemonic_is_valid(mnemonic.split(' ')):
            raise ValueError('Invalid mnemonic.')

        self._mnemonic = mnemonic
        self._public_key, self._private_key = mnemonic_to_private_key(mnemonic.split(' '))

        data_cell = WalletV5R1.create_data_cell(
            self._public_key,
            wallet_id=self.wallet_id,
            network_global_id=-239,
        )
        state_init = StateInit(code=WALLET_V5_R1_CODE, data=data_cell)
        self._address = Address((0, state_init.serialize().hash))

    @staticmethod
    def create_internal_message(destination: str, amount: int, body: str) -> WalletMessage:
        return WalletV5R1.create_wallet_internal_message(
            destination=Address(destination),
            value=amount,
            body=body,
        )

    def create_transfer_message(
        self,
        seqno: int,
        messages: list[WalletMessage],
        valid_until: int,
    ) -> Cell:
        return WalletV5R1.raw_create_transfer_msg(
            WalletV5R1,
            private_key=self._private_key,
            seqno=seqno,
            wallet_id=self.wallet_id,
            messages=messages,
            valid_until=valid_until,
        )

    def create_external_message(self, body: Cell = None) -> MessageAny:
        return WalletV5R1.create_external_msg(dest=self.address, body=body)

    def create_external_transfer_message(
        self,
        seqno: int,
        *transfers: Transfer,
    ) -> tuple[str, str]:
        """
        Создает external transfer message.

        Возвращает (.to_boc.hex(), hash.hex())
        """
        messages = [
            self.create_internal_message(
                destination=i.address,
                amount=i.amount,
                body=i.payload,
            )
            for i in transfers
        ]
        tr_message = self.create_transfer_message(
            seqno,
            messages,
            max(transfers, key=lambda i: i.valid_until).valid_until,
        )
        ext = self.create_external_message(tr_message).serialize()
        return ext.to_boc().hex(), ext.hash.hex()

    @property
    def mnemonic(self) -> str:
        return self._mnemonic

    @property
    def wallet_id(self) -> int:
        return 2147483409

    @property
    def address(self) -> Address:
        return self._address


class Wallet:
    def __init__(self, offline_wallet: OfflineV5R1Wallet, provider: AutostarsProvider) -> None:
        self._offline_wallet = offline_wallet
        self._transfer_lock = asyncio.Lock()
        self._provider = provider
        self._last_info: TonAPIWallet | None = None

    @property
    def address(self) -> str:
        return self._offline_wallet.address.to_str()

    @property
    def offline_wallet(self) -> OfflineV5R1Wallet:
        return self._offline_wallet

    @property
    def provider(self) -> AutostarsProvider:
        return self._provider

    @classmethod
    async def from_mnemonics(cls, mnemonics: str, provider: AutostarsProvider) -> Self:
        wallet = OfflineV5R1Wallet(mnemonics)
        wallet_info = await provider.tonapi.get_wallet(wallet.address.to_str())
        if not wallet_info.is_wallet:
            raise ValueError('Invalid wallet.')
        clss_ = cls(wallet, provider)
        clss_._last_info = wallet_info

    async def get_balance(self) -> int:
        return (await self.provider.tonapi.get_wallet(self.address)).balance

    async def transfer(self, *transfers: Transfer, seqno: int | None = None) -> tuple[str, str]:
        if seqno is None:
            seqno = (await self.provider.tonapi.get_seqno(self.address)).seqno

        msg = self.offline_wallet.create_external_transfer_message(seqno, *transfers)
        await self.provider.tonapi.send_message(boc=msg[0])
        return msg

    async def wait_for_transfer(self, msg_hash: str, valid_until: int) -> str: ...
