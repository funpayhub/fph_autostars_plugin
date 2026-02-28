from __future__ import annotations

from typing import TYPE_CHECKING

from funpaybotengine.dispatching.events import NewSaleEvent

from ..types import StarsOrder
from ..types.enums import StarsOrderType


if TYPE_CHECKING:
    from funpaybotengine.dispatching.events import Event


_CATEGORY_TEXTS = {'Telegram, Звёзды', 'Telegram, Stars'}


async def extract_stars_orders(events: list[Event], hub_instance: str) -> list[StarsOrder]:
    if not (order_events := [i for i in events if isinstance(i, NewSaleEvent)]):
        return []

    result = []
    for event in order_events:
        preview = await event.get_order_preview()
        if preview.category_text.strip() not in _CATEGORY_TEXTS:
            continue

        obj = StarsOrder(
            message_obj=event.message,
            order_preview=await event.get_order_preview(),
            telegram_username=StarsOrder.get_telegram_username(preview.title),
            hub_instance=hub_instance,
        )
        if obj.type is not StarsOrderType.BY_USERNAME:
            continue
        result.append(obj)

    return result
