from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from autostars.src import events
from autostars.src.other import NotificationChannels
from autostars.src.types import StarsOrder
from autostars.src.logger import logger
from autostars.src.formatters import StarsOrderCategory, StarsOrderFormatterContext

from funpayhub.lib.plugin import LoadedPlugin
from funpayhub.lib.hub.text_formatters.category import InCategory

from funpayhub.app.formatters import GeneralFormattersCategory
from funpayhub.app.dispatching.router import Router


if TYPE_CHECKING:
    from autostars.src.plugin import AutostarsPlugin
    from autostars.src.properties import AutostarsProperties

    from funpayhub.app.main import FunPayHub as FPH


router = Router(name='autostars_events')


async def default_hook(hub: FPH, order: StarsOrder, msg_text: str, hook_name: str):
    if not msg_text:
        return

    try:
        pack = await hub.funpay.text_formatters.format_text(
            text=msg_text,
            context=StarsOrderFormatterContext(stars_order=order),
            query=InCategory(StarsOrderCategory).or_(InCategory(GeneralFormattersCategory)),
        )
    except Exception:
        logger.error('Ошибка форматирования сообщения (%s).', hook_name, exc_info=True)
        return

    try:
        await hub.funpay.send_messages_stack(pack, order.funpay_chat_id)
    except Exception:
        logger.error('Ошибка отправки сообщения (%s).', hook_name, exc_info=True)
        return


async def on_username_not_found(self, order: StarsOrder) -> None:
    asyncio.create_task(
        self.default_hook(
            order,
            self.plugin.props.messages.username_not_found_message.value,
            'Telegram username not found',
        ),
    )


async def on_username_invalid(self, order: StarsOrder) -> None:
    asyncio.create_task(
        self.default_hook(
            order,
            self.plugin.props.messages.invalid_username_message.value,
            'Invalid telegram username',
        ),
    )


async def on_not_user_username(self, order: StarsOrder) -> None:
    asyncio.create_task(
        self.default_hook(
            order,
            self.plugin.props.messages.not_user_username_message.value,
            'Not user username',
        ),
    )


async def on_username_fetch_error(self, order: StarsOrder) -> None:
    asyncio.create_task(
        self.default_hook(
            order,
            self.plugin.props.messages.failed_to_fetch_username_message.value,
            'Error fetching telegram username',
        ),
    )


@router.on_event(event_filter=events.StarsOrdersPackCompletedEvent.__event_name__, as_task=True)
async def send_success_telegram_notification(stars_orders: list[StarsOrder], hub: FPH):
    message_text = '<b>✅ Транзакции по заказам {order_ids} успешно выполнены.</b>'.format(
        order_ids=', '.join(f'<code>{i.order_id}</code>' for i in stars_orders),
    )
    hub.telegram.send_notification(NotificationChannels.INFO, message_text)


@router.on_event(event_filter=events.StarsOrderCompletedEvent.__event_name__, as_task=True)
async def send_funpay_message(
    stars_order: StarsOrder,
    plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties],
    hub: FPH,
):
    if not plugin.properties.messages.transaction_completed_message.value:
        return

    await default_hook(
        hub,
        stars_order,
        plugin.properties.messages.transaction_completed_message.value,
        'transaction_completed_message',
    )
