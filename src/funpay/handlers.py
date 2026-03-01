from __future__ import annotations

import re
import asyncio
from typing import TYPE_CHECKING
from itertools import chain
from collections import defaultdict

from funpaybotengine import Router
from autostars.src.logger import logger
from autostars.src.exceptions import FragmentResponseError
from autostars.src.formatters import StarsOrderCategory, StarsOrderFormatterContext
from autostars.src.types.enums import ErrorTypes, StarsOrderStatus
from autostars.src.autostars_provider import AutostarsProvider

from funpayhub.lib.translater import _ru
from funpayhub.lib.hub.text_formatters.category import InCategory

from funpayhub.app.formatters import GeneralFormattersCategory

from .utils import extract_stars_orders


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder
    from autostars.src.plugin import AutostarsPlugin
    from funpaybotengine.types import Message
    from funpaybotengine.runner import EventsStack
    from autostars.src.properties import AutostarsProperties
    from autostars.src.fragment_api import FragmentAPI

    from funpayhub.lib.plugin import LoadedPlugin

    from funpayhub.app.main import FunPayHub as FPH


router = Router(name='autostars')
username_re = re.compile(r'@?[a-zA-Z0-9_]{4,32}')
orderid_re = re.compile(r'[A-Z0-9]{8}')


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


async def check_usernames(orders: list[StarsOrder], provider: AutostarsProvider):
    checked: dict[StarsOrderStatus, list[StarsOrder]] = defaultdict(list)
    storage = provider.storage

    to_check: list[StarsOrder] = []
    for order in orders:
        if not order.telegram_username or not username_re.fullmatch(order.telegram_username):
            order.status = StarsOrderStatus.WAITING_FOR_USERNAME
            checked[order.status].append(order)
        elif provider.fragmentapi is None:
            order.status = StarsOrderStatus.ERROR
            order.error = ErrorTypes.FRAGMENT_API_NOT_PROVIDED
            checked[order.status].append(order)
        else:
            to_check.append(order)

    r = await asyncio.gather(*(check_username(i, provider.fragmentapi) for i in to_check))
    for i in r:
        checked[i.status].append(i)
    await storage.add_or_update_orders(*chain(*checked.values()))

    # todo: send notification to funpay
    # todo: send notification in chat if error occurred while fetching username


@router.on_new_events_pack(
    lambda events_stack, hub: len(events_stack.events) > 1 and hub.funpay.authenticated,
    handler_id='Save telegram stars orders',
)
async def sale_orders(
    events_stack: EventsStack, hub: FPH, autostars_provider: AutostarsProvider
) -> None:
    orders = await extract_stars_orders(events_stack.events, hub.instance_id)
    if not orders:
        return

    logger.info(_ru('Добавляю данные о заказах %s в базу данных.'), [i.order_id for i in orders])

    await autostars_provider.storage.add_or_update_orders(*orders)
    asyncio.create_task(check_usernames(orders, autostars_provider))


@router.on_new_message(lambda message: message.text.startswith('/stars'))
async def update_order_username(message: Message, autostars_provider: AutostarsProvider, hub: FPH):
    args = message.text.split(' ')[1:]
    if len(args) < 2:
        return

    order_id, username = args[0], args[1]

    if not orderid_re.fullmatch(order_id) or username_re.fullmatch(username):
        return

    order = await autostars_provider.storage.get_order(order_id)
    if not order or order.funpay_chat_id != message.chat_id:
        return

    if order.hub_instance != hub.instance_id:
        return  # todo: toggle in settings

    if order.status is not StarsOrderStatus.WAITING_FOR_USERNAME and not (
        order.status is StarsOrderStatus.ERROR
        and order.error is ErrorTypes.UNABLE_TO_FETCH_USERNAME
    ):
        return

    order.telegram_username = username
    await autostars_provider.storage.add_or_update_orders(order)
    asyncio.create_task(check_usernames([order], autostars_provider))
