from __future__ import annotations

import re
import asyncio
from typing import TYPE_CHECKING
from itertools import chain
from collections import defaultdict

from funpaybotengine import Router
from autostars.src.logger import logger
from autostars.src.exceptions import FragmentResponseError
from autostars.src.types.enums import ErrorTypes, StarsOrderStatus
from autostars.src.autostars_provider import AutostarsProvider

from funpayhub.lib.translater import _ru

from .utils import extract_stars_orders


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder
    from funpaybotengine.types import Message
    from funpaybotengine.runner import EventsStack
    from autostars.src.callbacks import Callbacks
    from autostars.src.fragment_api import FragmentAPI

    from funpayhub.app.main import FunPayHub as FPH


router = Router(name='autostars')
username_re = re.compile(r'@?[a-zA-Z0-9_]{4,32}')
orderid_re = re.compile(r'[A-Z0-9]{8}')


async def check_username(o: StarsOrder, api: FragmentAPI) -> StarsOrder:
    for i in range(3):
        try:
            r = await api.search_stars_recipient(o.telegram_username)
            o.status, o.recipient_id = StarsOrderStatus.READY, r.found.recipient
            return o
        except FragmentResponseError:
            o.status = StarsOrderStatus.WAITING_FOR_USERNAME
            return o
        except Exception:
            logger.warning('Ошибка проверки @%s (%d).', o.telegram_username, i + 1, exc_info=True)
            await asyncio.sleep(1)
    o.status = StarsOrderStatus.ERROR
    o.error = ErrorTypes.UNABLE_TO_FETCH_USERNAME
    o.retries_left = 0
    return o


async def check_usernames(orders: list[StarsOrder], provider: AutostarsProvider, cbs: Callbacks):
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

    if checked[StarsOrderStatus.WAITING_FOR_USERNAME]:
        asyncio.create_task(
            cbs.on_username_not_found(*checked[StarsOrderStatus.WAITING_FOR_USERNAME]),
        )

    # todo: send notification in chat if error occurred while fetching username


@router.on_new_events_pack(
    lambda events_stack, hub: len(events_stack.events) > 1 and hub.funpay.authenticated,
    handler_id='Save telegram stars orders',
)
async def sale_orders(
    events_stack: EventsStack,
    hub: FPH,
    autostars_provider: AutostarsProvider,
    autostars_callbacks: Callbacks,
) -> None:
    orders = await extract_stars_orders(events_stack.events, hub.instance_id)
    if not orders:
        return

    logger.info(_ru('Добавляю данные о заказах %s в базу данных.'), [i.order_id for i in orders])

    await autostars_provider.storage.add_or_update_orders(*orders)
    asyncio.create_task(check_usernames(orders, autostars_provider, autostars_callbacks))


@router.on_new_message(lambda message: message.text.startswith('/stars'))
async def update_order_username(
    message: Message,
    autostars_provider: AutostarsProvider,
    hub: FPH,
    autostars_callbacks: Callbacks,
):
    args = message.text.split(' ')[1:]
    if len(args) < 2:
        return

    order_id, username = args[0], args[1].replace('@', '')

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
    asyncio.create_task(check_usernames([order], autostars_provider, autostars_callbacks))
