from __future__ import annotations


__all__ = [
    'StarsOrderMenuContext',
    'OldOrdersListMenuContext',
    'OrdersListMenuContext'
]


from autostars.src.types.enums import StarsOrderStatus

from funpayhub.lib.telegram.ui import MenuContext

# For pydantic models
from autostars.src.types import StarsOrder


class StarsOrderMenuContext(MenuContext):
    stars_order: StarsOrder


class OldOrdersListMenuContext(MenuContext):
    orders_status: StarsOrderStatus


class OrdersListMenuContext(MenuContext):
    header_text: str | None = None
    orders: list[StarsOrder]
