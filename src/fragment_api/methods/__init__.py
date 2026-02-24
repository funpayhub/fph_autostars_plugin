from __future__ import annotations


__all__ = [
    'FragmentMethod',
    'SearchStarsRecipient',
    'InitBuyStarsRequest',
    'GetBuyStarsLink',
]

from .base import FragmentMethod
from .methods import GetBuyStarsLink, InitBuyStarsRequest, SearchStarsRecipient
