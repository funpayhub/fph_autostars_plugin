from __future__ import annotations

from typing import TYPE_CHECKING
from json import JSONDecodeError

from aiohttp import TCPConnector, ClientSession, ClientResponseError
from pydantic import ValidationError
from autostars.src.exceptions import ParsingError, UnexpectedStatus, FragmentResponseError


if TYPE_CHECKING:
    from autostars.src.fragment_api.methods.base import FragmentMethod


class Session:
    def __init__(self, session: ClientSession | None = None) -> None:
        self._session = session
        self._connector: TCPConnector | None = None
        self._headers: dict[str, str] = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Host': 'fragment.com',
            'Origin': 'https://fragment.com',
            'Referer': 'https://fragment.com/stars/buy',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'X-Requested-With': 'XMLHttpRequest',
        }

    async def session(self) -> ClientSession:
        if not self._session or self._session.closed:
            self._connector = TCPConnector()
            self._session = ClientSession(
                connector=self._connector,
                connector_owner=False,
                base_url='https://fragment.com/',
                headers=self._headers,
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> ClientSession:
        return await self.session()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def post[ReturnT](
        self,
        method: FragmentMethod[ReturnT],
        cookies: str,
        hash: str,
    ) -> ReturnT:
        """
        raises: FragmentSessionError
        """
        session = await self.session()
        data = {str(k): str(v) for k, v in method.model_dump(mode='json', by_alias=True).items()}
        async with session.post(
            'api',
            params={'hash': hash},
            headers={'Cookie': cookies},
            data=data,
        ) as r:
            try:
                r.raise_for_status()
            except ClientResponseError as e:
                raise UnexpectedStatus(method.method, e.status) from e

            try:
                parsed = await r.json()
            except JSONDecodeError as e:
                raise ParsingError(method_name=method.method) from e

            if parsed.get('error'):
                raise FragmentResponseError(method.method, parsed['error'])

            try:
                return method.__model_to_build__.model_validate(parsed)
            except ValidationError as e:
                raise ParsingError(method_name=method.method) from e
