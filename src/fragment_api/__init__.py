from __future__ import annotations

from typing import TYPE_CHECKING

from temp.autostars.src.fragment_api.methods import GetBuyStarsLink, InitBuyStarsRequest, SearchStarsRecipient
from temp.autostars.src.fragment_api.session import Session


if TYPE_CHECKING:
    from temp.autostars.src.fragment_api.types import BuyStarsLink, BuyStarsResponse, RecipientResponse


class FragmentAPIProvider:
    def __init__(self) -> None:
        self.api: FragmentAPI | None = None


class FragmentAPI:
    def __init__(self, cookies: str, hash: str):
        self._cookies = cookies
        self._hash = hash
        self.session = Session()

    @property
    def cookies(self) -> str:
        return self._cookies

    @property
    def hash(self) -> str:
        return self._hash

    async def search_stars_recipient(self, username: str) -> RecipientResponse:
        return await self.session.post(
            SearchStarsRecipient(query=username),
            self.cookies,
            self.hash,
        )

    async def init_buy_stars_request(
        self,
        recipient: str,
        quantity: int = 50,
    ) -> BuyStarsResponse:
        return await self.session.post(
            InitBuyStarsRequest(recipient=recipient, quantity=quantity),
            self.cookies,
            self.hash,
        )

    async def get_buy_stars_link(self, request_id: str) -> BuyStarsLink:
        return await self.session.post(
            GetBuyStarsLink(request_id=request_id),
            self.cookies,
            self.hash,
        )

    async def auto_get_buy_stars_link(self, username: str, quantity: int = 50) -> BuyStarsLink:
        recipient = await self.search_stars_recipient(username)
        init = await self.init_buy_stars_request(recipient.found.recipient, quantity)
        return await self.get_buy_stars_link(init.request_id)
