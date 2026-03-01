from __future__ import annotations


__all__ = ['Callbacks']


import asyncio
from typing import TYPE_CHECKING
from autostars.src.plugin import AutostarsPlugin
from funpayhub.app.main import FunPayHub
from autostars.src.logger import logger
from funpayhub.lib.translater import _ru
from autostars.src.formatters import StarsOrderFormatterContext, StarsOrderCategory
from funpayhub.app.formatters import GeneralFormattersCategory
from funpayhub.lib.hub.text_formatters.category import InCategory
from autostars.src.other import NotificationChannels


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder



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

    async def generate_payload_text(self, order: StarsOrder, ref: str) -> str:
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

    async def on_username_not_found(self, order: StarsOrder) -> None:
        await self.default_hook(
            order,
            self.plugin.props.messages.username_not_found_message.value,
            'Invalid telegram username',
        )

    async def on_username_fetch_error(self, order: StarsOrder) -> None:
        ...  # todo: add parameter

    async def on_transaction_started(self, order: StarsOrder) -> None:
        await self.default_hook(
            order,
            self.plugin.props.messages.transaction_started_message.value,
            'Transaction started',
        )

    async def on_successful_transaction(self, *orders: StarsOrder) -> None:
        for order in orders:
            asyncio.create_task(self.default_hook(
                order,
                self.plugin.props.messages.transaction_completed_message.value,
                'Successful transaction',
            ))

        message_text = self.hub.translater.translate(
            '<b>✅ Транзакции по заказам {order_ids} успешно выполнены.</b>',
        ).format(
            order_ids=', '.join(f'<code>{i.order_id}</code>' for i in orders),
        )
        self.hub.telegram.send_notification(NotificationChannels.INFO, message_text)

    async def on_transactions_error(self, *orders: StarsOrder) -> None:
        for order in orders:
            asyncio.create_task(self.default_hook(
                order,
                self.plugin.props.messages.transaction_failed_message.value,
                'Transaction error',
            ))

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