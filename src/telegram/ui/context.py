from __future__ import annotations


__all__ = ['StarsOrderMenuContext', 'OldOrdersMenuContext']


from typing import TYPE_CHECKING
from dataclasses import dataclass

from autostars.src.types.enums import StarsOrderStatus

from funpayhub.lib.telegram.ui import MenuContext


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder


@dataclass(kw_only=True)
class StarsOrderMenuContext(MenuContext):
    stars_order: StarsOrder


@dataclass(kw_only=True)
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


@dataclass(kw_only=True)
class OldOrdersListMenuContext(MenuContext):
    orders_status: StarsOrderStatus
    orders: list[StarsOrder]

    def __post_init__(self) -> None:
        super().__post_init__()
        if isinstance(self.orders_status, str):
            self.orders_status = StarsOrderStatus(self.orders_status)
