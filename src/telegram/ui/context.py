from __future__ import annotations


__all__ = [
    'StarsOrderMenuContext',
    'OldOrdersMenuContext',
    'OldOrdersListMenuContext',
    'OrdersListMenuContext'
]


from typing import TYPE_CHECKING

from autostars.src.types.enums import StarsOrderStatus

from funpayhub.lib.telegram.ui import MenuContext


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder


class StarsOrderMenuContext(MenuContext):
    stars_order: StarsOrder


class OldOrdersMenuContext(MenuContext):
    unprocessed_orders: int
    waiting_username_orders: int
    ready_orders: int
    errored_orders: int

    @property
    def total_len(self) -> int:
        return (
            self.unprocessed_orders
            + self.waiting_username_orders
            + self.ready_orders
            + self.errored_orders
        )


class OldOrdersListMenuContext(MenuContext):
    orders_status: StarsOrderStatus
    orders: list[StarsOrder]


class OrdersListMenuContext(MenuContext):
    header_text: str | None = None
    orders: list[StarsOrder]
