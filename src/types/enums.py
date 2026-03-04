from __future__ import annotations


__all__ = [
    'StarsOrderType',
    'StarsOrderStatus',
    'ErrorTypes',
]
from enum import Enum


class StarsOrderType(Enum):
    BY_USERNAME = 'BY_USERNAME'
    BY_ACCOUNT = 'BY_ACCOUNT'
    BY_GIFT = 'BY_GIFT'
    UNKNOWN = 'UNKNOWN'

    @classmethod
    def from_offer_title(cls, offer_title: str) -> StarsOrderType:
        vals = {
            'по username': StarsOrderType.BY_USERNAME,
            'by username': StarsOrderType.BY_USERNAME,
            'подарком': StarsOrderType.BY_GIFT,
            'подарунком': StarsOrderType.BY_GIFT,
            'as a gift': StarsOrderType.BY_GIFT,
            'с заходом на аккаунт': StarsOrderType.BY_ACCOUNT,
            'зi входом в акаунт': StarsOrderType.BY_ACCOUNT,
            'by logging in to the account': StarsOrderType.BY_ACCOUNT,
        }
        for k, v in vals.items():
            if k in offer_title.lower():
                return v
        return StarsOrderType.UNKNOWN


class StarsOrderStatus(Enum):
    UNPROCESSED = 'UNPROCESSED'
    WAITING_FOR_USERNAME = 'WAITING_FOR_USERNAME'
    READY = 'READY'
    PREPARING_TRANSFER = 'PREPARING_TRANSFER'
    TRANSFERRING = 'TRANSFERRING'
    DONE = 'DONE'
    ERROR = 'ERROR'

    @property
    def desc(self) -> str:
        return _status_desc.get(self, self.name)


_status_desc = {
    StarsOrderStatus.UNPROCESSED: 'Не обработан',
    StarsOrderStatus.WAITING_FOR_USERNAME: 'Ожидается юзернейм',
    StarsOrderStatus.READY: 'Готов к исполнению',
    StarsOrderStatus.PREPARING_TRANSFER: 'Подготавливается перевод',
    StarsOrderStatus.TRANSFERRING: 'Выполняется перевод TON',
    StarsOrderStatus.DONE: 'Выполнен',
    StarsOrderStatus.ERROR: 'Завершен с ошибкой'
}


class ErrorTypes(Enum):
    UNABLE_TO_FETCH_STARS_LINK = 'UNABLE_TO_FETCH_STARS_LINK'
    GET_BALANCE_ERROR = 'GET_BALANCE_ERROR'
    NOT_ENOUGH_TON = 'NOT_ENOUGH_TON'
    TRANSFER_ERROR = 'TRANSFER_ERROR'
    TRANSACTION_TIMEOUT_ERROR = 'TRANSACTION_TIMEOUT_ERROR'

    INVALID_USERNAME = 'INVALID_USERNAME'
    USERNAME_NOT_FOUND = 'USERNAME_NOT_FOUND'
    NOT_USER_USERNAME = 'NOT_USER_USERNAME'
    UNABLE_TO_FETCH_USERNAME = 'UNABLE_TO_FETCH_USERNAME'
    FRAGMENT_API_NOT_PROVIDED = 'FRAGMENT_API_NOT_PROVIDED'

    @property
    def desc(self) -> str:
        return _error_desc.get(self, self.name)


_error_desc = {
    ErrorTypes.UNABLE_TO_FETCH_STARS_LINK: 'Не удалось получить данные для перевода TON (ошибка Fragment API)',
    ErrorTypes.GET_BALANCE_ERROR: 'Не удалось получить баланс TON кошелька',
    ErrorTypes.NOT_ENOUGH_TON: 'Недостаточно TON',
    ErrorTypes.TRANSFER_ERROR: 'Не удалось инициализировать перевод TON',
    ErrorTypes.TRANSACTION_TIMEOUT_ERROR: 'Таймаут ожидания подтверждения транзакции',
    ErrorTypes.INVALID_USERNAME: 'Невалидные Telegram юзернейм (не подходит по паттерну)',
    ErrorTypes.USERNAME_NOT_FOUND: 'Telegram юзернейм не найден',
    ErrorTypes.NOT_USER_USERNAME: 'Telegram юзернейм принадлежит не пользователю',
    ErrorTypes.UNABLE_TO_FETCH_USERNAME: 'Не удалось получить данные о Telegram юзернейме (ошибка Fragment API)',
    ErrorTypes.FRAGMENT_API_NOT_PROVIDED: 'Fragment cookies или hash не указаны в настройках или невалидны'
}
