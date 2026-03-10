from __future__ import annotations


__all__ = ['Callbacks']


import asyncio
from typing import TYPE_CHECKING

from autostars.src.other import NotificationChannels
from autostars.src.logger import logger
from autostars.src.formatters import StarsOrderCategory, StarsOrderFormatterContext
from autostars.src import events

from funpayhub.lib.translater import _ru
from funpayhub.lib.hub.text_formatters.category import InCategory

from funpayhub.app.main import FunPayHub
from funpayhub.app.formatters import GeneralFormattersCategory


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

    async def gen_payload(self, order: StarsOrder, ref: str) -> str:
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
        await self.hub.dispatcher.event_entry(
            events.StarsOrdersPackUsernameCheckFailed(list(orders))
        )
        for i in orders:
            await self.hub.dispatcher.event_entry(events.StarsOrderUsernameCheckFailed(i))

    async def on_successful_transaction(self, *orders: StarsOrder) -> None:
        await self.hub.dispatcher.event_entry(events.StarsOrdersPackCompletedEvent(list(orders)))
        for i in orders:
            await self.hub.dispatcher.event_entry(events.StarsOrderCompletedEvent(i))

    async def on_transactions_error(self, *orders: StarsOrder) -> None:
        await self.hub.dispatcher.event_entry(events.StarsOrdersPackFailedEvent(list(orders)))
        for i in orders:
            await self.hub.dispatcher.event_entry(events.StarsOrderFailedEvent(i))

    @property
    def hub(self) -> FunPayHub:
        return self._hub

    @property
    def plugin(self) -> AutostarsPlugin:
        return self._plugin
