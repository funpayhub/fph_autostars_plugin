from __future__ import annotations

__all__ = ['StarsOrderMenuContext']


from typing import TYPE_CHECKING

from funpayhub.lib.telegram.ui import MenuContext
from dataclasses import dataclass

if TYPE_CHECKING:
    from autostars.src.types import StarsOrder


@dataclass(kw_only=True)
class StarsOrderMenuContext(MenuContext):
    stars_order: StarsOrder
