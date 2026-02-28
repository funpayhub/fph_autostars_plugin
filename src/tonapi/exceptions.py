from __future__ import annotations

from autostars.src.exceptions import AutostarsPluginException
from funpayhub.lib.translater import _ru


class TonAPIError(AutostarsPluginException): ...


class TonAPISessionError(TonAPIError): ...


class TonAPIParsingError(TonAPISessionError):
    def __init__(self, method_path: str) -> None:
        super().__init__(_ru('Произошла при парсиге ответа на метод %s.'), method_path)

        self.method_path = method_path


class TonAPIUnexpectedStatus(TonAPISessionError):
    def __init__(self, method_path: str, status: int, error: str | None = None) -> None:
        super().__init__(
            _ru('Произошла ошибка при запросе %s. Статус: %s. Ошиюка %s'),
            method_path,
            status,
            error
        )
        self.method_path = method_path
        self.error = error
        self.status = status
