from __future__ import annotations


__all__ = ['BUILDERS']


from .builders import (
    StatusMenuBuilder,
    OldOrdersListMenuBuilder,
    StarsOrderInfoMenuBuilder,
    OldOrdersNotificationMenuBuilder,
    OrdersListMenuBuilder
)


BUILDERS = [
    StarsOrderInfoMenuBuilder,
    StatusMenuBuilder,
    OldOrdersNotificationMenuBuilder,
    OldOrdersListMenuBuilder,
    OrdersListMenuBuilder
]
