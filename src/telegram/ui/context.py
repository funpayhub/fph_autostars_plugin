from __future__ import annotations


__all__ = ['StarsOrderMenuContext', 'OldOrdersMenuContext']


from typing import TYPE_CHECKING
from dataclasses import dataclass

from funpayhub.lib.telegram.ui import MenuContext


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder


@dataclass(kw_only=True)
class StarsOrderMenuContext(MenuContext):
    stars_order: StarsOrder


@dataclass(kw_only=True)
class OldOrdersMenuContext(MenuContext):
    waiting_username_orders: list[StarsOrder]
    errored_orders: list[StarsOrder]

    @property
    def total_len(self) -> int:
        return len(self.waiting_username_orders) + len(self.errored_orders)