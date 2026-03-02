from __future__ import annotations

from typing import Any

from funpaybotengine.dispatching import OrderEvent, NewMessageEvent

from funpayhub.lib.hub.text_formatters import Formatter
from funpayhub.lib.hub.text_formatters.category import FormatterCategory
from pydantic import Field

from funpayhub.app.formatters import (
    NewOrderContext,
    OrderFormattersCategory,
    MessageFormattersCategory,
)

from .types import StarsOrder


class StarsOrderFormatterContext(NewOrderContext):
    order_event: OrderEvent = Field(default=None)
    goods_to_deliver: list[str] = Field(default_factory=list)
    new_message_event: NewMessageEvent = Field(default=None)
    stars_order: StarsOrder

    def model_post_init(self, context: Any, /) -> None:
        self.order_event = self.stars_order.sale_event
        self.new_message_event = self.order_event.related_new_message_event


DESC = (
    'Форматтер для заказов Telegram Stars.\n\n'
    'Позволяет вставлять информацию о заказе, TON транзации и т.д.\n'
    'Можно использовать во всех сообщениях плагина Telegram Stars.\n\n'
    '1. <code>$autostars&lt;telegram_username&gt;</code>\n'
    'Подставляет Telegram username, который на данный момент привязан к заказу.\n'
    'Можно так же использовать <code>$autostars_username</code>.\n\n'
    '2. <code>$autostars&lt;stars_amount&gt;</code>\n'
    'Подставляет общее кол-во звезд, которые были/будут отправлены.\n'
    'Можно так же использовать <code>$autostars_amount</code>.\n\n'
    '3. <code>$autostars&lt;transaction_hash&gt;</code>\n'
    'Подставляет хэш TON транзакции, связанную с заказом. Если транзации несуществует '
    '(например, форматтер используется в сообщении об ошибке), подставляет пустую строку.\n'
    'Можно так же использовать <code>$autostars_hash</code>.\n\n'
    '4. <code>$autostars&lt;recipient_id&gt;</code>\n'
    'Подставляет Telegram ID получателя из Fragment API.\n'
    'Можно так же использовать <code>$autostars_recipient_id</code>.\n\n'
    '5. <code>$autostars&lt;ref&gt;</code>\n'
    'Подставляет Ref транзакции из Fragment API.\n'
    'Можно так же использовать <code>$autostars_ref</code>.'
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
        if self.mode == 'transaction_hash':
            return self.context.stars_order.transaction_hash or ''
        if self.mode == 'telegram_username':
            return self.context.stars_order.telegram_username or ''
        if self.mode == 'stars_amount':
            return str(self.context.stars_order.stars_amount)
        return ''


class AutostarsHashFormatter(
    Formatter[StarsOrderFormatterContext],
    key='autostars_hash',
    name='🌟 Autostars hash ($autostars_hash)',
    description='Подставляет хэш TON транзакции, связанную с заказом. Если транзации несуществует '
    '(например, форматтер используется в сообщении об ошибке), подставляет пустую строку.\n'
    'Можно так же использовать <code>$autostars&lt;transaction_hash&gt;</code>.',
    context_type=StarsOrderFormatterContext,
):
    def __init__(
        self,
        context: StarsOrderFormatterContext,
        *args,
        **kwargs
    ):
        super().__init__(context, *args)

    def format(self) -> str:
        return self.context.stars_order.transaction_hash or ''


class AutostarsUsernameFormatter(
    Formatter[StarsOrderFormatterContext],
    key='autostars_username',
    name='🌟 Autostars username ($autostars_username)',
    description='Подставляет Telegram username, который на данный момент привязан к заказу.\n'
    'Можно так же использовать <code>$autostars&lt;telegram_username&gt;</code>.',
    context_type=StarsOrderFormatterContext,
):
    def __init__(
        self,
        context: StarsOrderFormatterContext,
        *args,
        **kwargs
    ):
        super().__init__(context, *args)

    def format(self) -> str:
        return self.context.stars_order.telegram_username or ''


class AutostarsStarsAmountFormatter(
    Formatter[StarsOrderFormatterContext],
    key='autostars_amount',
    name='🌟 Autostars amount ($autostars_amount)',
    description='Подставляет общее кол-во звезд, которые были/будут отправлены.\n'
    'Можно так же использовать <code>$autostars&lt;stars_amount&gt;</code>.',
    context_type=StarsOrderFormatterContext,
):
    def __init__(
        self,
        context: StarsOrderFormatterContext,
        *args,
        **kwargs
    ):
        super().__init__(context, *args)

    def format(self) -> str:
        return str(self.context.stars_order.stars_amount) or ''


class AutostarsRecipientIDFormatter(
    Formatter[StarsOrderFormatterContext],
    key='autostars_recipient_id',
    name='🌟 Autostars recipient ID ($autostars_recipient_id)',
    description='Подставляет Telegram ID получателя из Fragment API.\n'
    'Можно так же использовать <code>$autostars&lt;recipient_id&gt;</code>.',
    context_type=StarsOrderFormatterContext,
):
    def __init__(
        self,
        context: StarsOrderFormatterContext,
        *args,
        **kwargs
    ):
        super().__init__(context, *args)

    def format(self) -> str:
        return self.context.stars_order.recipient_id or ''


class AutostarsRefFormatter(
    Formatter[StarsOrderFormatterContext],
    key='autostars_ref',
    name='🌟 Autostars ref ($autostars_ref)',
    description='Подставляет Ref транзакции из Fragment API.\n'
    'Можно так же использовать <code>$autostars&lt;ref&gt;</code>.',
    context_type=StarsOrderFormatterContext,
):
    def __init__(
        self,
        context: StarsOrderFormatterContext,
        *args,
        **kwargs
    ):
        super().__init__(context, *args)

    def format(self) -> str:
        return self.context.stars_order.ref or ''


class StarsOrderCategory(FormatterCategory):
    id = 'autostars'
    name = 'Заказы Telegram Stars'
    description = 'Форматтеры, которые можно использовать в ответах к заказам Telegram Stars.'
    include_formatters = {
        StarsOrderFormatter.key,
        AutostarsHashFormatter.key,
        AutostarsUsernameFormatter.key,
        AutostarsStarsAmountFormatter.key,
        AutostarsRecipientIDFormatter.key,
        AutostarsRefFormatter.key,
    }
    include_categories = {MessageFormattersCategory.id, OrderFormattersCategory.id}


FORMATTERS = [
    StarsOrderFormatter,
    AutostarsHashFormatter,
    AutostarsUsernameFormatter,
    AutostarsStarsAmountFormatter,
    AutostarsRecipientIDFormatter,
    AutostarsRefFormatter
]
