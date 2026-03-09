from __future__ import annotations


__all__ = ['BUILDERS']


from .builders import (
    StatusMenuBuilder,
    StarsOrderInfoMenuBuilder,
    OldOrdersNotificationMenuBuilder,
    OldOrdersListMenuBuilder
)


BUILDERS = [
    StarsOrderInfoMenuBuilder,
    StatusMenuBuilder,
    OldOrdersNotificationMenuBuilder,
    OldOrdersListMenuBuilder
]
