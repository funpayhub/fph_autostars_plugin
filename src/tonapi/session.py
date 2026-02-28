from aiohttp import ClientSession, TCPConnector, ClientResponseError
from json import JSONDecodeError
from pydantic import ValidationError, BaseModel
from .methods import TonAPIMethod
from .exceptions import TonAPIError, TonAPIParsingError, TonAPIUnexpectedStatus
import time
import asyncio


class Session:
    def __init__(self, session: ClientSession | None = None) -> None:
        self._session = session
        self._connector: TCPConnector | None = None
        self._last_request_ts = 0
        self._headers = {
            'Accept': '*/*',
            'Content-Type': 'application/json',
        }

    async def session(self) -> ClientSession:
        if not self._session or self._session.closed:
            self._connector = TCPConnector()
            self._session = ClientSession(
                connector=self._connector,
                connector_owner=False,
                base_url='https://tonapi.io/',
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

    async def _make_request[ReturnT](self, method: TonAPIMethod[ReturnT]) -> ReturnT:
        if time.monotonic() - self._last_request_ts < 1.1:
            await asyncio.sleep(time.monotonic() - self._last_request_ts + 1.1)
        session = await self.session()
        data = method.model_dump_json(by_alias=True)
        path = method.get_path()
        call = session.get(url=path) if method.method == 'GET' else session.post(url=path, data=data)
        print(path, data, sep='\n')
        async with call as r:
            self._last_request_ts = time.monotonic()
            try:
                r.raise_for_status()
            except ClientResponseError as e:
                try:
                    error = (await r.json(content_type=None)).get('error')
                except:
                    error = await r.text()
                raise TonAPIUnexpectedStatus(path, e.status, error) from e

            try:
                parsed = await r.json(content_type=None)
            except JSONDecodeError as e:
                raise TonAPIParsingError(method_path=path) from e

            if parsed and parsed.get('error'):
                raise TonAPIError(parsed['error'])

            try:
                if method.return_type is not None:
                    if issubclass(method.return_type, BaseModel):
                        return method.return_type.model_validate(parsed)
                    else:
                        return method.return_type(parsed)
            except ValidationError as e:
                raise TonAPIParsingError(method_path=path) from e

    async def make_request[ReturnT](self, method: TonAPIMethod[ReturnT]) -> ReturnT:
        try:
            return await self._make_request(method)
        except TonAPIError:
            raise
        except Exception as e:
            raise TonAPIError('Произошла ошибка при выполнении запроса %s', method.get_path()) from e