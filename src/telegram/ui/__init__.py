from __future__ import annotations


__all__ = ['BUILDERS']


from .builders import (
    StatusMenuBuilder,
    StarsOrderInfoMenuBuilder,
    OldOrdersNotificationMenuBuilder,
)


BUILDERS = [StarsOrderInfoMenuBuilder, StatusMenuBuilder, OldOrdersNotificationMenuBuilder]
