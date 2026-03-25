from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from autostars.src import events
from autostars.src.other import NotificationChannels
from autostars.src.logger import logger
from autostars.src.formatters import StarsOrderCategory, StarsOrderFormatterContext
from autostars.src.telegram.ui.context import OrdersListMenuContext
from autostars.src.types.enums import ErrorTypes, StarsOrderStatus
from autostars.src.autostars_provider import AutostarsProvider
from funpayhub.lib.telegram.ui import UIRegistry

from funpayhub.lib.translater import (
    ru as _ru,
    translater,
)
from funpayhub.lib.hub.text_formatters.category import InCategory

from funpayhub.app.formatters import GeneralFormattersCategory
from funpayhub.app.dispatching.router import Router


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder
    from autostars.src.properties import AutostarsProperties

    from funpayhub.app.main import FunPayHub as FPH


router = Router(name='autostars:internal_events')
ru = translater.translate


async def send_funpay_notification(hub: FPH, order: StarsOrder, msg_text: str, hook_name: str):
    if not msg_text:
        return

    try:
        pack = await hub.funpay.text_formatters.format_text(
            text=msg_text,
            context=StarsOrderFormatterContext(stars_order=order),
            query=InCategory(StarsOrderCategory).or_(InCategory(GeneralFormattersCategory)),
        )
    except Exception:
        logger.error(_ru('Ошибка форматирования сообщения (%s).'), hook_name, exc_info=True)
        return

    try:
        await hub.funpay.send_messages_stack(pack, order.funpay_chat_id)
    except Exception:
        logger.error(_ru('Ошибка отправки сообщения (%s).'), hook_name, exc_info=True)
        return


@router.on_event(event_filter=events.StarsOrdersPackCompletedEvent.__event_name__)
async def success_tg_notification(
    hub: FPH,
    event: events.StarsOrdersPackCompletedEvent,
    tg_ui: UIRegistry
):
    menu = await OrdersListMenuContext(
        menu_id='autostars:orders_list',
        header_text=ru('<b>✅ Транзакции по заказам успешно выполнены.</b>'),
        orders=event.stars_orders
    ).build_menu(tg_ui)
    hub.telegram.send_notification(
        NotificationChannels.INFO,
        menu.total_text,
        reply_markup=menu.total_keyboard(convert=True)
    )


@router.on_event(event_filter=events.StarsOrdersPackFailedEvent.__event_name__)
async def err_tg_notification(
    hub: FPH,
    event: events.StarsOrdersPackFailedEvent,
    tg_ui: UIRegistry
):
    orders = [i for i in event.stars_orders if not i.retries_left]
    if not orders:
        return

    menu = await OrdersListMenuContext(
        menu_id='autostars:orders_list',
        chat_id=-1,
        header_text=ru('<b>❌ Ошибка при переводе TON.</b>'),
        orders=orders
    ).build_menu(tg_ui)

    hub.telegram.send_notification(
        NotificationChannels.ERROR,
        menu.total_text,
        reply_markup=menu.total_keyboard(convert=True)
    )


@router.on_event(event_filter=events.StarsOrdersPackUsernameCheckFailed.__event_name__)
async def err_username_notification(
    hub: FPH,
    event: events.StarsOrdersPackFailedEvent,
    tg_ui: UIRegistry
):
    menu = await OrdersListMenuContext(
        menu_id='autostars:orders_list',
        chat_id=-1,
        header_text=ru(
            '<b>❌ Ошибка при проверке юзернейма '
            '(покупателям необходимо попробовать позже с помощью команды '
            '<code>/stars ORDERID</code>).</b>'
        ),
        orders=event.stars_orders
    ).build_menu(tg_ui)

    hub.telegram.send_notification(
        NotificationChannels.ERROR,
        menu.total_text,
        reply_markup=menu.total_keyboard(convert=True)
    )


@router.on_event(event_filter=events.StarsOrderCompletedEvent.__event_name__)
async def success_fp_notification(
    stars_order: StarsOrder, plugin_properties: AutostarsProperties, hub: FPH
):
    await send_funpay_notification(
        hub,
        stars_order,
        plugin_properties.messages.transaction_completed_message.value,
        'Successful transaction',
    )


@router.on_event(
    lambda stars_order: not stars_order.retries_left,
    event_filter=events.StarsOrderFailedEvent.__event_name__,
    as_task=True,
)
async def failed_fp_notification(
    stars_order: StarsOrder, plugin_properties: AutostarsProperties, hub: FPH
):
    await send_funpay_notification(
        hub,
        stars_order,
        plugin_properties.messages.transaction_failed_message.value,
        'Failed transaction',
    )


@router.on_event(event_filter=events.StarsOrderUsernameCheckFailed.__event_name__, as_task=True)
async def bad_username_fp_notification(
    stars_order: StarsOrder,
    plugin_properties: AutostarsProperties,
    hub: FPH,
):
    ERROR_TYPES = {
        ErrorTypes.UNABLE_TO_FETCH_USERNAME: (
            plugin_properties.messages.failed_to_fetch_username_message.value,
            'Error fetching telegram username',
        ),
        ErrorTypes.INVALID_USERNAME: (
            plugin_properties.messages.invalid_username_message.value,
            'Invalid telegram username',
        ),
        ErrorTypes.NOT_USER_USERNAME: (
            plugin_properties.messages.not_user_username_message.value,
            'Not user username',
        ),
        ErrorTypes.USERNAME_NOT_FOUND: (
            plugin_properties.messages.username_not_found_message.value,
            'Username not found',
        ),
        ErrorTypes.BLOCKED_BY_USER: (
            plugin_properties.messages.blocked_by_user_message.value,
            'Blocked by user',
        ),
    }
    if stars_order.error not in ERROR_TYPES:
        return

    msg, hook_name = ERROR_TYPES[stars_order.error]
    await send_funpay_notification(hub, stars_order, msg, hook_name)


@router.on_event(
    lambda stars_order, plugin_properties: not stars_order.retries_left
    and plugin_properties.other.refund_on_error.value,
    event_filter=events.StarsOrderFailedEvent.__event_name__,
    as_task=True,
)
async def refund(stars_order: StarsOrder, autostars_provider: AutostarsProvider, hub: FPH):
    old_status = stars_order.status
    stars_order.status = StarsOrderStatus.REFUNDED
    await autostars_provider.storage.add_or_update_order(stars_order)

    for i in range(3):
        try:
            await hub.funpay.bot.refund(stars_order.order_id)
            break
        except Exception:
            logger.error(
                _ru('Не удалось вернуть средства по заказу %s.'),
                stars_order.order_id,
                exc_info=True,
            )
            await asyncio.sleep(1)
    else:
        stars_order.status = old_status
        await autostars_provider.storage.add_or_update_order(stars_order)
