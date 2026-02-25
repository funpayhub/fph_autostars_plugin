from __future__ import annotations

import time
import asyncio
from typing import TYPE_CHECKING, Self
from dataclasses import dataclass

from pytoniq import Address, LiteClient, WalletV5R1

from autostars.src.exceptions import TonWalletError
from autostars.src.utils import get_mainnet_config


if TYPE_CHECKING:
    from autostars.src.fragment_api.types import BuyStarsLink


@dataclass
class Transfer:
    address: str
    amount: int
    payload: str = ''
    valid_until: int | None = None

    def __post_init__(self) -> None:
        if self.valid_until is None:
            self.valid_until = int(time.time() + 60)

    @classmethod
    def from_buy_stars_link(cls, link: BuyStarsLink, payload: str = '') -> Self:
        return cls(
            address=link.transaction.messages[0].address,
            amount=link.transaction.messages[0].amount,
            valid_until=link.transaction.valid_until,
            payload=payload,
        )


class WalletProvider:
    def __init__(self):
        self.wallet = None

    async def remake_wallet(self, mnemonics: str) -> None:
        self.wallet = await Wallet.from_mnemonics(mnemonics)


class Wallet:
    def __init__(self, client: LiteClient, wallet: WalletV5R1):
        self._client = client
        self._wallet = wallet
        self._transfer_lock = asyncio.Lock()

    @property
    def client(self) -> LiteClient:
        return self._client

    @property
    def address(self) -> str:
        return self._wallet.address.to_str()

    @property
    def wallet(self) -> WalletV5R1:
        return self._wallet

    @classmethod
    async def _from_mnemonics(cls, mnemonics: str) -> Self:
        config = await get_mainnet_config()

        for i in range(len(config['liteservers'])):
            client = LiteClient.from_config(config=config, trust_level=3, ls_i=i, timeout=2)
            try:
                await client.connect()
                break
            except Exception:
                continue
        else:
            raise RuntimeError('Unable to connect to LiteServer.')

        wallet = await WalletV5R1.from_mnemonic(
            provider=client,
            mnemonics=mnemonics,
            network_global_id=-239,
        )

        return cls(client, wallet)

    @classmethod
    async def from_mnemonics(cls, mnemonics: str) -> Self:
        try:
            return await cls._from_mnemonics(mnemonics)
        except Exception as e:
            raise TonWalletError('Unable to connect to wallet.') from e

    @classmethod
    async def testnet_from_mnemonics(cls, mnemonics: str) -> Self:
        client = LiteClient.from_testnet_config(trust_level=3)
        await client.connect()
        wallet = await WalletV5R1.from_mnemonic(
            provider=client,
            mnemonics=mnemonics,
            network_global_id=-3,
        )
        return cls(client, wallet)

    async def get_balance(self) -> int:
        return await self.wallet.get_balance()

    async def _transfer(self, *transfers: Transfer) -> str:
        seqno = await self.wallet.get_seqno()
        messages = [
            self.wallet.create_wallet_internal_message(
                destination=Address(i.address),
                value=i.amount,
                body=i.payload,
            )
            for i in transfers
        ]
        transfer_msg = self.wallet.raw_create_transfer_msg(
            private_key=self.wallet.private_key,
            seqno=seqno,
            wallet_id=self.wallet.wallet_id,
            messages=messages,
            valid_until=max(transfers, key=lambda i: i.valid_until).valid_until,
        )
        await self.wallet.send_external(body=transfer_msg)
        return transfer_msg.hash.hex()

    async def transfer(self, *transfers: Transfer) -> str:
        valid_until = max(transfers, key=lambda i: i.valid_until).valid_until
        async with self._transfer_lock:
            hash = await self._transfer(*transfers)
            tr = await self.wait_for_transfer(hash, valid_until)
            return tr

    async def wait_for_transfer(self, hash: str, valid_until: int) -> str:
        first = True

        while True:
            if first:
                first = False
            else:
                await asyncio.sleep(1)

            t = time.time()
            try:
                transactions = await self.client.get_transactions(self.wallet.address, count=10)
            except:
                continue  # todo

            for i in transactions:
                if i.in_msg.body.hash.hex() == hash:
                    return i.cell.hash.hex()
            else:
                if t > valid_until:
                    raise TimeoutError(
                        f'Transfer {hash} timed out after {valid_until - t} seconds',
                    )
