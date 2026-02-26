from __future__ import annotations

from funpaybotengine.dispatching import NewMessageEvent, OrderEvent
from pydantic import Field

from funpayhub.lib.hub.text_formatters import Formatter
from funpayhub.lib.hub.text_formatters.category import FormatterCategory

from funpayhub.app.formatters import (
    NewOrderContext,
    OrderFormattersCategory,
    MessageFormattersCategory,
)
from typing import Any

from temp.autostars.src.types import StarsOrder


class StarsOrderFormatterContext(NewOrderContext):
    new_message_event: NewMessageEvent = Field(default=None)
    order_event: OrderEvent = Field(default=None)
    goods_to_deliver: list[str] = Field(default_factory=list)
    stars_order: StarsOrder

    def model_post_init(self, context: Any) -> None:
        self.order_event = self.stars_order.sale_event
        self.new_message_event = self.order_event.related_new_message_event


DESC = (
    'Форматтер для заказов Telegram Stars.\n\n'
    'Позволяет вставлять информацию о заказе, TON транзации и т.д.\n'
    'Можно использовать во всех сообщениях плагина Telegram Stars.\n\n'
    'Необходимо использовать с одним обязательным параметром - режимом вставки:\n'
    '<code>ton_transaction_id</code>, <code>telegram_username</code>, <code>stars_amount</code>.\n\n'
    '1. <code>$autostars&lt;ton_transaction_id&gt;</code>\n'
    'Подставляет TON транзакцию, связанную с заказом. Если транзации несуществует '
    '(например, форматтер используется в сообщении об ошибке), подставляет пустую строку.\n\n'
    '2. <code>$autostars&lt;telegram_username&gt;</code>\n'
    'Подставляет Telegram username, который на данный момент привязан к заказу.\n\n'
    '3. <code>$autostars&lt;stars_amount&gt;</code>\n'
    'Подставляет общее кол-во звезд, которые были/будут отправлены.\n\n'
)


class StarsOrderFormatter(
    Formatter[StarsOrderFormatterContext],
    key='autostars',
    name='🌟 Autostars ($autostars)',
    description=DESC,
    context_type=StarsOrderFormatterContext,
):
    def __init__(
        self,
        context: StarsOrderFormatterContext,
        mode: str = '',
        *args,
        **kwargs,
    ) -> None:
        super().__init__(context, *args)
        self.mode = mode

    def format(self) -> str:
        if self.mode == 'ton_transaction_id':
            return self.context.stars_order.ton_transaction_id or ''
        if self.mode == 'telegram_username':
            return self.context.stars_order.telegram_username or ''
        if self.mode == 'stars_amount':
            return str(self.context.stars_order.stars_amount)
        return ''


class StarsOrderCategory(FormatterCategory):
    id = 'autostars'
    name = 'Заказы Telegram Stars'
    description = 'Форматтеры, которые можно использовать в ответах к заказам Telegram Stars.'
    include_formatters = {StarsOrderFormatter.key}
    include_categories = {MessageFormattersCategory.id, OrderFormattersCategory.id}
