from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from funpaybotengine.dispatching.events import NewSaleEvent

from autostars.src.types import StarsOrder
from autostars.src.types.enums import StarsOrderType


if TYPE_CHECKING:
    from funpaybotengine.dispatching.events import Event


category_names = {'Telegram, Звёзды', 'Telegram, Stars'}


async def extract_stars_orders(
    events: Iterable[Event],
    hub_instance: str,
    stars_type: StarsOrderType | list[StarsOrderType] = StarsOrderType.BY_USERNAME,
) -> list[StarsOrder]:
    if not isinstance(stars_type, list):
        stars_type = [stars_type]

    order_events = [
        i
        for i in events
        if isinstance(i, NewSaleEvent) and i.__event_name__ == NewSaleEvent.__event_name__
    ]
    if not order_events:
        return []

    result = []
    for event in order_events:
        preview = await event.get_order_preview()
        if preview.category_text.strip() not in category_names:
            continue

        obj = StarsOrder(
            message_obj=event.message,
            order_preview=await event.get_order_preview(),
            telegram_username=StarsOrder.get_telegram_username(preview.title),
            hub_instance=hub_instance,
        )
        if obj.type not in stars_type:
            continue
        result.append(obj)

    return result
