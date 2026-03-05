from __future__ import annotations


__all__ = ['BUILDERS']


from .builders import StarsOrderInfoMenuBuilder, StatusMenuBuilder, OldOrdersNotificationMenuBuilder


BUILDERS = [StarsOrderInfoMenuBuilder, StatusMenuBuilder, OldOrdersNotificationMenuBuilder]
