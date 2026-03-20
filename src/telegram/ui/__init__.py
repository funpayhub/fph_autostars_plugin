from __future__ import annotations


__all__ = ['BUILDERS']


from .builders import (
    StatusMenuBuilder,
    OldOrdersListMenuBuilder,
    StarsOrderInfoMenuBuilder,
    OldOrdersMenuBuilder,
    OrdersListMenuBuilder
)


BUILDERS = [
    StarsOrderInfoMenuBuilder,
    StatusMenuBuilder,
    OldOrdersMenuBuilder,
    OldOrdersListMenuBuilder,
    OrdersListMenuBuilder
]
