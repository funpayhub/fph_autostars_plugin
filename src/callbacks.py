from __future__ import annotations
from typing import TYPE_CHECKING
from autostars.src.plugin import AutostarsPlugin
from funpayhub.app.main import FunPayHub
from autostars.src.logger import logger
from funpayhub.lib.translater import _ru
from autostars.src.formatters import StarsOrderFormatterContext, StarsOrderCategory
from funpayhub.app.formatters import GeneralFormattersCategory
from funpayhub.lib.hub.text_formatters.category import InCategory


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder


class Callbacks:
    def __init__(self, plugin: AutostarsPlugin) -> None:
        self._hub = plugin.hub
        self._plugin = plugin

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

    async def on_successful_transaction(self, order: StarsOrder) -> None:
        await self.default_hook(
            order,
            self.plugin.props.messages.transaction_completed_message.value,
            'Successful transaction',
        )
        # todo: telegram notification in INFO channel

    async def on_transaction_error(self, order: StarsOrder) -> None:
        await self.default_hook(
            order,
            self.plugin.props.messages.transaction_failed_message.value,
            'Transaction error',
        )
        # todo: telegram notification in ERROR channel

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