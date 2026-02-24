from __future__ import annotations

from typing import TYPE_CHECKING

from funpaybotengine.dispatching.events import NewSaleEvent

from ..types import StarsOrder
from ..types.enums import StarsOrderType


if TYPE_CHECKING:
    from funpaybotengine.dispatching.events import Event


async def extract_stars_orders(
    events: list[Event],
    category_text: str,
    hub_instance: str,
    stars_type: StarsOrderType | list[StarsOrderType] = StarsOrderType.BY_USERNAME,
) -> list[StarsOrder]:
    if not isinstance(stars_type, list):
        stars_type = [stars_type]
    category_text = category_text.strip()
    print(f'{category_text=}')

    order_events = [
        i
        for i in events
        if isinstance(i, NewSaleEvent) and i.__event_name__ == NewSaleEvent.__event_name__
    ]
    if not order_events:
        print('No order events')
        return []

    result = []
    for event in order_events:
        preview = await event.get_order_preview()
        if preview.category_text.strip() != category_text:
            print(f'{preview.id} - Wrong category: {preview.category_text.strip()}')
            continue

        obj = StarsOrder(
            message_obj=event.message,
            order_preview=await event.get_order_preview(),
            telegram_username=StarsOrder.get_telegram_username(preview.title),
            hub_instance=hub_instance,
        )
        if obj.type not in stars_type:
            print(f'{preview.id} - Wrong stars type: {obj.type}')
            continue
        result.append(obj)

    return result
