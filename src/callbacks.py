from __future__ import annotations


__all__ = ['Callbacks']


import asyncio
from typing import TYPE_CHECKING

from autostars.src.other import NotificationChannels
from autostars.src.logger import logger
from autostars.src.formatters import StarsOrderCategory, StarsOrderFormatterContext
from autostars.src.types.enums import ErrorTypes

from funpayhub.lib.translater import _ru
from funpayhub.lib.hub.text_formatters.category import InCategory

from funpayhub.app.main import FunPayHub
from funpayhub.app.formatters import GeneralFormattersCategory
from collections import defaultdict


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder
    from autostars.src.plugin import AutostarsPlugin


AD_TEXT = (
    '✨ Звезды переведены автоматически плагином AutoStars для бесплатного бота FunPay Hub.  \n\n'
    '💻 GitHub: https://github.com/funpayhub/funpayhub \n'
    '💻 Plugin GitHub: https://github.com/funpayhub/fph_autostars_plugin \n'
    '✈️ Telegram: https://t.me/funpay_hub'
)


class Callbacks:
    def __init__(self, plugin: AutostarsPlugin) -> None:
        self._hub = plugin.hub
        self._plugin = plugin

    async def pyload_factory(self, order: StarsOrder, ref: str) -> str:
        text = f'{AD_TEXT}\n\n{ref}' if self.plugin.props.messages.show_ad.value else ref
        if not self.plugin.props.messages.payload_message.value:
            return text

        try:
            pack = await self.hub.funpay.text_formatters.format_text(
                text=self.plugin.props.messages.payload_message.value,
                context=StarsOrderFormatterContext(stars_order=order),
                query=InCategory(StarsOrderCategory).or_(InCategory(GeneralFormattersCategory)),
            )
        except Exception:
            logger.error(_ru('Ошибка форматирования комментария к транзакции.'), exc_info=True)
            return text

        return ''.join(i for i in pack.entries if isinstance(i, str)) + f'\n\n{text}'

    async def on_username_check_error(self, *orders: StarsOrder) -> None:
        errors: dict[ErrorTypes, list[StarsOrder]] = defaultdict(list)
        for order in orders:
            errors[order.error].append(order)

        if err_fetch_username := errors[ErrorTypes.UNABLE_TO_FETCH_USERNAME]:
            asyncio.create_task(self.on_username_fetch_error(*err_fetch_username))
        if err_invalid_username := errors[ErrorTypes.INVALID_USERNAME]:
            asyncio.create_task(self.on_username_invalid(*err_invalid_username))
        if err_not_user_username := errors[ErrorTypes.NOT_USER_USERNAME]:
            asyncio.create_task(self.on_not_user_username(*err_not_user_username))
        if err_username_not_found := errors[ErrorTypes.USERNAME_NOT_FOUND]:
            asyncio.create_task(self.on_username_not_found(*err_username_not_found))

    async def on_username_not_found(self, *orders: StarsOrder) -> None:
        for order in orders:
            asyncio.create_task(
                self.default_hook(
                    order,
                    self.plugin.props.messages.username_not_found_message.value,
                    'Telegram username not found',
                )
            )

    async def on_username_invalid(self, *orders: StarsOrder) -> None:
        for order in orders:
            asyncio.create_task(
                self.default_hook(
                    order,
                    self.plugin.props.messages.invalid_username_message.value,
                    'Invalid telegram username',
                )
            )


    async def on_not_user_username(self, *orders: StarsOrder) -> None:
        for order in orders:
            asyncio.create_task(
                self.default_hook(
                    order,
                    self.plugin.props.messages.not_user_username_message.value,
                    'Not user username'
                )
            )

    async def on_username_fetch_error(self, *orders: StarsOrder) -> None:
        for order in orders:
            asyncio.create_task(
                self.default_hook(
                    order,
                    self.plugin.props.messages.failed_to_fetch_username_message.value,
                    'Error fetching telegram username'
                )
            )

        # todo: send telegram notification

    async def on_transaction_started(self, order: StarsOrder) -> None:
        await self.default_hook(
            order,
            self.plugin.props.messages.transaction_started_message.value,
            'Transaction started',
        )

    async def on_successful_transaction(self, *orders: StarsOrder) -> None:
        for order in orders:
            asyncio.create_task(
                self.default_hook(
                    order,
                    self.plugin.props.messages.transaction_completed_message.value,
                    'Successful transaction',
                )
            )

        message_text = self.hub.translater.translate(
            '<b>✅ Транзакции по заказам {order_ids} успешно выполнены.</b>',
        ).format(
            order_ids=', '.join(f'<code>{i.order_id}</code>' for i in orders),
        )
        self.hub.telegram.send_notification(NotificationChannels.INFO, message_text)

    async def on_transactions_error(self, *orders: StarsOrder) -> None:
        for order in orders:
            asyncio.create_task(
                self.default_hook(
                    order,
                    self.plugin.props.messages.transaction_failed_message.value,
                    'Transaction error',
                )
            )

        message_text = self.hub.translater.translate(
            '<b>❌ Ошибка при трансфере TON для заказов {order_ids}.</b>',
        ).format(
            order_ids=', '.join(f'<code>{i.order_id}</code>' for i in orders),
        )
        self.hub.telegram.send_notification(NotificationChannels.ERROR, message_text)

    async def default_hook(self, order: StarsOrder, msg_text: str, hook_name: str):
        if not msg_text:
            return

        try:
            pack = await self.hub.funpay.text_formatters.format_text(
                text=msg_text,
                context=StarsOrderFormatterContext(stars_order=order),
                query=InCategory(StarsOrderCategory).or_(InCategory(GeneralFormattersCategory)),
            )
        except Exception:
            logger.error(_ru('Ошибка форматирования сообщения (%s).'), hook_name, exc_info=True)
            return

        try:
            await self.hub.funpay.send_messages_stack(pack, order.funpay_chat_id)
        except Exception:
            logger.error(_ru('Ошибка отправки сообщения (%s).'), hook_name, exc_info=True)
            return

    @property
    def hub(self) -> FunPayHub:
        return self._hub

    @property
    def plugin(self) -> AutostarsPlugin:
        return self._plugin
