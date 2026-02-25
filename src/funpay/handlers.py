from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
from itertools import chain
from collections import defaultdict

from funpaybotengine import Router
from autostars.src.exceptions import FragmentResponseError
from autostars.src.formatters import StarsOrderCategory, StarsOrderFormatterContext
from autostars.src.types.enums import ErrorTypes, StarsOrderStatus
from funpaybotengine.types.enums import SubcategoryType

from funpayhub.lib.translater import _ru
from funpayhub.lib.hub.text_formatters.category import InCategory

from funpayhub.app.formatters import GeneralFormattersCategory


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder
    from autostars.src.plugin import AutostarsPlugin
    from autostars.src.storage import Storage
    from funpaybotengine.runner import EventsStack
    from autostars.src.properties import AutostarsProperties
    from autostars.src.fragment_api import FragmentAPI, FragmentAPIProvider

    from funpayhub.lib.plugin import LoadedPlugin

    from funpayhub.app.main import FunPayHub as FPH


from .utils import extract_stars_orders


router = Router(name='autostars')


TELEGRAM_CATEGORY_ID = 224
STARS_SUBCATEGORY_ID = 2418


async def check_username(
    order: StarsOrder, api: FragmentAPI, logger: logging.Logger
) -> StarsOrder:
    for attempt in range(3):
        try:
            r = await api.search_stars_recipient(order.telegram_username)
            order.status = StarsOrderStatus.READY
            order.recipient_id = r.found.recipient
            return order
        except FragmentResponseError:
            order.status = StarsOrderStatus.WAITING_FOR_USERNAME
            return order
        except Exception:
            logger.warning(
                'Не удалось проверить Telegram username %s. Попытка: %d/3.',
                order.telegram_username,
                attempt + 1,
                exc_info=True,
            )
            await asyncio.sleep(1)
    order.status = StarsOrderStatus.ERROR
    order.error = ErrorTypes.UNABLE_TO_FETCH_USERNAME
    order.retries_left = 0
    return order


async def check_usernames(
    orders: list[StarsOrder],
    storage: Storage,
    api_provider: FragmentAPIProvider,
    plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties],
):
    checked: dict[StarsOrderStatus, list[StarsOrder]] = defaultdict(list)

    to_check: list[StarsOrder] = []
    for order in orders:
        if not order.telegram_username:
            order.status = StarsOrderStatus.WAITING_FOR_USERNAME
            checked[order.status].append(order)
        elif api_provider.api is None:
            order.status = StarsOrderStatus.ERROR
            order.error = ErrorTypes.FRAGMENT_API_NOT_PROVIDED
            checked[order.status].append(order)
        else:
            to_check.append(order)

    r = await asyncio.gather(
        *(check_username(i, api_provider.api, plugin.plugin.logger) for i in to_check)
    )
    for i in r:
        checked[i.status].append(i)
    await storage.add_or_update_orders(*chain(*checked.values()))

    # todo: send notification to funpay
    # todo: send notification in chat if error occurred while fetching username


async def on_username_not_found(
    order: StarsOrder,
    plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties],
) -> None:
    text = plugin.properties.messages.username_not_found_message.value
    if not text:
        return

    ctx = StarsOrderFormatterContext(
        new_message_event=order.sale_event.related_new_message_event,
        order_event=order.sale_event,
        goods_to_deliver=[],
        stars_order=order,
    )

    try:
        pack = await plugin.plugin.hub.funpay.text_formatters.format_text(
            text=text,
            context=ctx,
            query=InCategory(StarsOrderCategory).or_(InCategory(GeneralFormattersCategory)),
        )
    except Exception:
        plugin.plugin.logger.error(
            _ru('Не удалось форматировать сообщение о неверном telegram юзернейме.'),
            exc_info=True,
        )
        # todo: notification
        return

    try:
        await plugin.plugin.hub.funpay.send_messages_stack(pack, order.funpay_chat_id)
    except Exception:
        plugin.plugin.logger.error(
            _ru('Не удалось отправить сообщение о неверном telegram юзернейме.'),
            exc_info=True,
        )
        # todo: notification
        return


@router.on_new_events_pack(
    lambda events_stack, hub: len(events_stack.events) > 1 and hub.funpay.authenticated,
    handler_id='Save telegram stars orders',
)
async def sale_orders(
    events_stack: EventsStack,
    hub: FPH,
    autostars_storage: Storage,
    plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties],
    autostars_fragment_api: FragmentAPIProvider,
) -> None:
    cat = await hub.funpay.bot.storage.get_category(TELEGRAM_CATEGORY_ID)
    subcat = [
        i
        for i in cat.subcategories
        if i.type == SubcategoryType.OFFERS and i.id == STARS_SUBCATEGORY_ID
    ][0]

    name = f'{cat.name}, {subcat.name}'
    stars_orders = await extract_stars_orders(events_stack.events, name, hub.instance_id)
    if not stars_orders:
        plugin.plugin.logger.debug(
            _ru('Нет событий о продаже связанных с Telegram stars. Events pack: %s.'),
            events_stack.id,
        )
        return

    plugin.plugin.logger.info(
        _ru('Добавляю данные о заказах %s в базу данных.'),
        [i.order_id for i in stars_orders],
    )

    await autostars_storage.add_or_update_orders(*stars_orders)
    asyncio.create_task(
        check_usernames(stars_orders, autostars_storage, autostars_fragment_api, plugin),
    )
