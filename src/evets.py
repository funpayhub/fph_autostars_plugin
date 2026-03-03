__all__ = [
    'AutostarsEvent',
    'StarsOrderCompletedEvent',
    'StarsOrderFailedEvent',
    'StarsOrdersPackCompletedEvent',
    'StarsOrderPackFailedEvent'
]

from typing import Any

from funpayhub.app.dispatching.events.base import HubEvent
from autostars.src.types import StarsOrder


class AutostarsEvent(HubEvent, event_name='__autostars_event__'): ...


class StarsOrderCompletedEvent(AutostarsEvent, event_name='autostars:stars_order_completed'):
    def __init__(self, stars_order: StarsOrder) -> None:
        super().__init__()
        self._stars_order = stars_order

    @property
    def stars_order(self) -> StarsOrder:
        return self._stars_order

    @property
    def event_context_injection(self) -> dict:
        return super().event_context_injection | {'stars_order': self.stars_order}


class StarsOrderFailedEvent(AutostarsEvent, event_name='autostars:stars_order_failed'):
    def __init__(self, stars_order: StarsOrder) -> None:
        super().__init__()
        self._stars_order = stars_order

    @property
    def stars_order(self) -> StarsOrder:
        return self._stars_order

    @property
    def event_context_injection(self) -> dict[str, Any]:
        return super().event_context_injection | {'stars_order': self.stars_order}


class StarsOrdersPackCompletedEvent(AutostarsEvent, event_name='autostars:stars_orders_pack_completed'):
    def __init__(self, stars_orders: list[StarsOrder]) -> None:
        super().__init__()
        self._stars_orders = stars_orders

    @property
    def stars_orders(self) -> list[StarsOrder]:
        return self._stars_orders

    @property
    def event_context_injection(self) -> dict[str, Any]:
        return super().event_context_injection | {'stars_orders': self.stars_orders}


class StarsOrderPackFailedEvent(AutostarsEvent, event_name='autostars:stars_orders_pack_failed'):
    def __init__(self, stars_orders: list[StarsOrder]) -> None:
        super().__init__()
        self._stars_orders = stars_orders

    @property
    def stars_orders(self):
        return self._stars_orders

    @property
    def event_context_injection(self) -> dict[str, Any]:
        return super().event_context_injection | {'stars_orders': self.stars_orders}