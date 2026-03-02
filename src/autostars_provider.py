from __future__ import annotations

from typing import TYPE_CHECKING

from autostars.src.ton import Wallet
from autostars.src.fragment_api import FragmentAPI


if TYPE_CHECKING:
    from autostars.src.tonapi import TonAPI
    from autostars.src.storage import Storage


class AutostarsProvider:
    def __init__(
        self,
        tonapi: TonAPI,
        storage: Storage,
        fragmentapi: FragmentAPI | None = None,
        wallet: Wallet | None = None,
    ):
        self._storage = storage
        self._tonapi = tonapi
        self._fragmentapi = fragmentapi
        self._wallet = wallet

    async def change_wallet(self, mnemonic: str) -> Wallet | None:
        self._wallet = await Wallet.from_mnemonics(mnemonic, self) if mnemonic else None
        return self._wallet

    async def change_fragment_api(self, cookies: str, hash: str) -> FragmentAPI | None:
        self._fragmentapi = FragmentAPI(cookies, hash) if cookies and hash else None
        return self._fragmentapi

    @property
    def storage(self) -> Storage:
        return self._storage

    @property
    def tonapi(self) -> TonAPI:
        return self._tonapi

    @property
    def fragmentapi(self) -> FragmentAPI | None:
        return self._fragmentapi

    @property
    def wallet(self) -> Wallet | None:
        return self._wallet
