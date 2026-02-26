from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import BaseMiddleware


if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from autostars.src.properties import AutostarsProperties

    from funpayhub.lib.telegram.callback_data import UnknownCallback


class CryMiddleware(BaseMiddleware):
    def __init__(self, props: AutostarsProperties):
        self.props = props

    async def __call__(self, handler, event: CallbackQuery, data):
        await handler(event, data)
        await self.answer(event)

    async def answer(self, event: CallbackQuery):
        parsed: UnknownCallback | None = getattr(event, '__parsed__', None)
        if parsed is None:
            return

        if (
            parsed.identifier == 'next_param_value'
            and parsed.data.get('path') == self.props.messages.show_ad.path
            and not self.props.messages.show_ad.value
        ):
            await event.answer(
                '☹️ Ну и пожалуйста. Ну и больно надо. Доволен, да? Ну вот и сиди теперь.',
                show_alert=True,
            )
