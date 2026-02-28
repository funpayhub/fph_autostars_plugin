from __future__ import annotations

from funpayhub.lib.exceptions import TranslatableException
from funpayhub.lib.translater import _ru


class AutostarsPluginException(TranslatableException): ...


class FragmentException(AutostarsPluginException): ...


class FragmentSessionError(AutostarsPluginException): ...


class FragmentParsingError(FragmentSessionError):
    def __init__(self, method_name: str) -> None:
        super().__init__(
            _ru('Произошла при парсиге ответа на метод %s.'),
            method_name,
        )

        self.method_name = method_name


class FragmentUnexpectedStatus(FragmentSessionError):
    def __init__(self, method_name: str, status: int) -> None:
        super().__init__(
            _ru('Произошла ошибка при запросе %s. Статус: %s.'),
            method_name,
            status,
        )

        self.method_name = method_name
        self.status = status


class FragmentResponseError(FragmentSessionError):
    def __init__(self, method_name: str, error_text: str) -> None:
        super().__init__(
            _ru('Произошла ошибка при запросе %s: %s.'),
            method_name,
            error_text,
        )

        self.method_name = method_name
        self.error_text = error_text


class FragmentAPIError(FragmentException): ...


class FragmentUsernameNotFound(FragmentAPIError):
    def __init__(self, username: str) -> None:
        super().__init__(
            _ru('Telegram username %s не найден.'),
            username,
        )
        self.username = username


class FailedInitRequest(FragmentAPIError):
    def __init__(self) -> None:
        super().__init__(
            _ru('Ошибка при запросе на инициализацию перевода звезд.'),
        )


class FailedToCreateStarsLink(FragmentAPIError):
    def __init__(self) -> None:
        super().__init__(
            _ru('Ошибка при создании ссылки на перевод звезд.'),
        )


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
