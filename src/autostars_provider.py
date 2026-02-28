from __future__ import annotations
from typing import TYPE_CHECKING

from autostars.src.fragment_api import FragmentAPI
from autostars.src.ton import Wallet

if TYPE_CHECKING:
    from autostars.src.tonapi import TonAPI


class AutostarsProvider:
    def __init__(
        self,
        tonapi: TonAPI,
        fragmentapi: FragmentAPI,
        wallet: Wallet | None = None,
    ):
        self._tonapi = tonapi
        self._fragmentapi = fragmentapi
        self._wallet = wallet

    @property
    def tonapi(self) -> TonAPI:
        return self._tonapi

    @property
    def fragmentapi(self) -> FragmentAPI:
        return self._fragmentapi

    @property
    def wallet(self) -> Wallet | None:
        return self._wallet