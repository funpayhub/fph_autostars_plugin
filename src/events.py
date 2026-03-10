from __future__ import annotations


__all__ = [
    'AutostarsEvent',
    'SingleOrderEvent',
    'OrdersPackEvent',
    'StarsOrderCompletedEvent',
    'StarsOrderFailedEvent',
    'StarsOrderUsernameCheckFailed',
    'StarsOrdersPackCompletedEvent',
    'StarsOrdersPackFailedEvent',
    'StarsOrdersPackUsernameCheckFailed',
]

from typing import Any

from autostars.src.types import StarsOrder

from funpayhub.app.dispatching.events.base import HubEvent


class AutostarsEvent(HubEvent, event_name='__autostars_event__'): ...


class SingleOrderEvent(AutostarsEvent, event_name='__autostars__single_order_event__'):
    def __init__(self, order: StarsOrder) -> None:
        super().__init__()
        self._stars_order = order

    @property
    def stars_order(self) -> StarsOrder:
        return self._stars_order

    @property
    def event_context_injection(self) -> dict:
        return super().event_context_injection | {'stars_order': self.stars_order}


class OrdersPackEvent(AutostarsEvent, event_name='__autostars_orders_pack_event__'):
    def __init__(self, stars_orders: list[StarsOrder]) -> None:
        super().__init__()
        self._stars_orders = stars_orders

    @property
    def stars_orders(self):
        return self._stars_orders

    @property
    def event_context_injection(self) -> dict[str, Any]:
        return super().event_context_injection | {'stars_orders': self.stars_orders}



class StarsOrderCompletedEvent(SingleOrderEvent, event_name='autostars:stars_order_completed'): ...


class StarsOrderFailedEvent(SingleOrderEvent, event_name='autostars:stars_order_failed'): ...


class StarsOrderUsernameCheckFailed(
    SingleOrderEvent,
    event_name='autostars:stars_order_username_failed'
): ...


class StarsOrdersPackCompletedEvent(
    OrdersPackEvent,
    event_name='autostars:stars_orders_pack_completed'
): ...


class StarsOrdersPackFailedEvent(
    OrdersPackEvent,
    event_name='autostars:stars_orders_pack_failed'
): ...

class StarsOrdersPackUsernameCheckFailed(
    OrdersPackEvent,
    event_name='autostars:stars_orders_pack_username_failed'
): ...
