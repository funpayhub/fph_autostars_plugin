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


_CHECK_USERNAME_ERRORS = {
    'no telegram users found.': ErrorTypes.USERNAME_NOT_FOUND,
    'please enter a username assigned to a user.': ErrorTypes.NOT_USER_USERNAME,
    'you can&#39;t gift telegram stars to this account at this moment.': ErrorTypes.BLOCKED_BY_USER,
}


CHECKING_ORDER_USERNAMES = set()


async def check_username(o: StarsOrder, api: FragmentAPI) -> StarsOrder:
    for i in range(3):
        try:
            r = await api.search_stars_recipient(o.telegram_username)
            o.status, o.recipient_id = StarsOrderStatus.READY, r.found.recipient
            return o
        except FragmentResponseError as e:
            o.status = StarsOrderStatus.WAITING_FOR_USERNAME
            o.error = _CHECK_USERNAME_ERRORS.get(
                e.error_text.lower(),
                ErrorTypes.UNABLE_TO_FETCH_USERNAME,
            )
            return o
        except Exception:
            logger.warning('Ошибка проверки @%s (%d).', o.telegram_username, i + 1, exc_info=True)
            await asyncio.sleep(1)
    o.status = StarsOrderStatus.WAITING_FOR_USERNAME
    o.error = ErrorTypes.UNABLE_TO_FETCH_USERNAME
    return o


async def check_usernames(orders: list[StarsOrder], provider: AutostarsProvider, cbs: Callbacks):
    global CHECKING_ORDER_USERNAMES
    order_ids = {i.order_id for i in orders}
    CHECKING_ORDER_USERNAMES.update(order_ids)

    checked: dict[StarsOrderStatus, list[StarsOrder]] = defaultdict(list)
    storage = provider.storage

    to_check: list[StarsOrder] = []
    for order in orders:
        if not order.telegram_username or not username_re.fullmatch(order.telegram_username):
            order.status = StarsOrderStatus.WAITING_FOR_USERNAME
            order.error = ErrorTypes.INVALID_USERNAME
            checked[order.status].append(order)
        elif provider.fragment is None:
            order.status = StarsOrderStatus.WAITING_FOR_USERNAME
            order.error = ErrorTypes.FRAGMENT_API_NOT_PROVIDED
            checked[order.status].append(order)
        else:
            to_check.append(order)

    r = await asyncio.gather(*(check_username(i, provider.fragment) for i in to_check))
    for i in r:
        checked[i.status].append(i)
    await storage.add_or_update_orders(*chain(*checked.values()))
    CHECKING_ORDER_USERNAMES.difference_update(order_ids)

    if checked[StarsOrderStatus.WAITING_FOR_USERNAME]:
        asyncio.create_task(
            cbs.on_username_check_error(*checked[StarsOrderStatus.WAITING_FOR_USERNAME]),
        )


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
    if len(args) < 1:
        return

    order_id = args[0]

    order = await autostars_provider.storage.get_order(order_id)
    if not order or order.funpay_chat_id != message.chat_id:
        return

    if order.hub_instance != hub.instance_id and not message.from_me:
        return

    if order.status is not StarsOrderStatus.WAITING_FOR_USERNAME:
        return

    if len(args) < 2 and order.error not in [
        ErrorTypes.UNABLE_TO_FETCH_USERNAME,
        ErrorTypes.BLOCKED_BY_USER,
    ]:
        return

    order.telegram_username = args[1] if len(args) > 1 else order.telegram_username
    order.status = StarsOrderStatus.WAITING_FOR_USERNAME

    await autostars_provider.storage.add_or_update_orders(order)
    asyncio.create_task(check_usernames([order], autostars_provider, autostars_callbacks))
