from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
from itertools import chain
from collections import defaultdict

from funpaybotengine import Router
from funpaybotengine.dispatching import OrderEvent

from autostars.src.exceptions import FragmentResponseError
from autostars.src.formatters import StarsOrderCategory, StarsOrderFormatterContext
from autostars.src.types.enums import ErrorTypes, StarsOrderStatus

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
    from funpaybotengine.types import Message
    from funpayhub.lib.plugin import LoadedPlugin

    from funpayhub.app.main import FunPayHub as FPH


from .utils import extract_stars_orders


router = Router(name='autostars')
logger = logging.getLogger('funpayhub.com_github_qvvonk_funpayhub_autostars_plugin')


async def check_username(order: StarsOrder, api: FragmentAPI) -> StarsOrder:
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
    plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties]
) -> None:
    checked: dict[StarsOrderStatus, list[StarsOrder]] = defaultdict(list)
    to_check: list[StarsOrder] = []
    api = plugin.plugin.fragment_api_provider.api

    for order in orders:
        if not order.telegram_username:
            order.status = StarsOrderStatus.WAITING_FOR_USERNAME
            checked[order.status].append(order)
        elif api is None:
            order.status = StarsOrderStatus.ERROR
            order.error = ErrorTypes.FRAGMENT_API_NOT_PROVIDED
            checked[order.status].append(order)
        else:
            to_check.append(order)

    for i in await asyncio.gather(*(check_username(i, api) for i in to_check)):
        checked[i.status].append(i)
    await plugin.plugin.storage.add_or_update_orders(*chain(*checked.values()))

    # temp
    for i in checked[StarsOrderStatus.WAITING_FOR_USERNAME]:
        asyncio.create_task(on_username_not_found(i, plugin))
    # todo: send notification in chat if error occurred while fetching username


async def on_username_not_found(
    order: StarsOrder,
    plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties],
) -> None:
    if not plugin.properties.messages.username_not_found_message.value:
        return

    try:
        pack = await plugin.plugin.hub.funpay.text_formatters.format_text(
            text=plugin.properties.messages.username_not_found_message.value,
            context=StarsOrderFormatterContext(stars_order=order),
            query=InCategory(StarsOrderCategory).or_(InCategory(GeneralFormattersCategory)),
        )
    except Exception:
        plugin.plugin.logger.error(
            _ru('Ошибка генерации сообщения о неверном telegram юзернейме.'),
            exc_info=True,
        )
        return

    try:
        await plugin.plugin.hub.funpay.send_messages_stack(pack, order.funpay_chat_id)
    except Exception:
        plugin.plugin.logger.error(
            _ru('Не удалось отправить сообщение о неверном telegram юзернейме.'),
            exc_info=True,
        )
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
) -> None:
    if not (stars_orders := await extract_stars_orders(events_stack.events, hub.instance_id)):
        return

    logger.info(
        _ru('Добавляю данные о заказах %s в базу данных.'),
        [i.order_id for i in stars_orders],
    )

    await autostars_storage.add_or_update_orders(*stars_orders)
    asyncio.create_task(check_usernames(stars_orders, plugin))


@router.on_new_message(
    lambda message: message.text and message.text.startswith('/stars '),
    as_task=True,
)
async def update_username(
    message: Message,
    autostars_storage: Storage,
    hub: FPH,
    plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties],
) -> None:
    args = message.text.split(' ')[1:]
    if len(args) < 2:
        return

    order_id, telegram_username = args[:2]
    if not (order := await autostars_storage.get_order(order_id)):
        return

    if order.funpay_chat_id != message.chat_id:
        return

    if order.status != StarsOrderStatus.WAITING_FOR_USERNAME or order.hub_instance != hub.instance_id:
        return

    order.telegram_username = telegram_username
    order.status = StarsOrderStatus.CHECKING_USERNAME
    await autostars_storage.add_or_update_order(order)
    await check_usernames([order], plugin)


@router.on_sale_refunded()
@router.on_sale_partially_refunded()
async def mark_as_refunded(event: OrderEvent, autostars_storage: Storage) -> None:
    preview = await event.get_preview()

    order = await autostars_storage.get_order(preview.order_id)
    if not order:
        return

    if order.status not in [StarsOrderStatus.READY, StarsOrderStatus.WAITING_FOR_USERNAME]:
        return

    order.status = StarsOrderStatus.REFUNDED
    await autostars_storage.add_or_update_order(order)
