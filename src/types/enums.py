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


class ErrorTypes(Enum):
    UNABLE_TO_FETCH_USERNAME = 'UNABLE_TO_FETCH_USERNAME'
    NOT_ENOUGH_TON = 'NOT_ENOUGH_TON'
    TRANSFER_ERROR = 'TRANSFER_ERROR'
    WALLET_NOT_PROVIDED = 'WALLET_NOT_PROVIDED'
    FRAGMENT_API_NOT_PROVIDED = 'FRAGMENT_API_NOT_PROVIDED'
    UNKNOWN = 'UNKNOWN'
