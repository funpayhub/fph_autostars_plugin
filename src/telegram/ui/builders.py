from __future__ import annotations

import html

from autostars.src.types.enums import ErrorTypes, StarsOrderStatus

from funpayhub.lib.telegram.ui import Menu, MenuBuilder
from funpayhub.lib.base_app.telegram.app.ui.ui_finalizers import StripAndNavigationFinalizer

from .context import StarsOrderMenuContext


_STATUSES = {
    StarsOrderStatus.UNPROCESSED: '⚫ Не обрабатывался',
    StarsOrderStatus.READY: '🟡 Готов к выполнению',
    StarsOrderStatus.TRANSFERRING: '⏳ Выполняется перевод',
    StarsOrderStatus.DONE: '🟢 Выполнен',
    StarsOrderStatus.WAITING_FOR_USERNAME: '❓ Ожидается Telegram юзернейм',
    StarsOrderStatus.ERROR: '❌ Произошла ошибка',
}


_ERRORS = {
    ErrorTypes.WALLET_NOT_PROVIDED: 'TON кошелек не инициализирован (сид фраза не была указана в настройках в момент заказа).',
    ErrorTypes.FRAGMENT_API_NOT_PROVIDED: 'Fragment API не инициализирован (cookie или hash не были указаны в настройках в момент заказа).',
    ErrorTypes.UNABLE_TO_FETCH_USERNAME: 'Ошибка Fragment API: не удалось проверить Telegram юзернейм.',
    ErrorTypes.NOT_ENOUGH_TON: 'Недостаточно TON.',
    ErrorTypes.TRANSFER_ERROR: 'Ошибка при переводе TON. Подробности в логах.',
    ErrorTypes.UNKNOWN: 'Неизвестная ошибка. Подробности в логах.',
}


class StarsOrderInfoMenuBuilder(
    MenuBuilder,
    menu_id='autostars:stars_order_info',
    context_type=StarsOrderMenuContext,
):
    async def build(self, ctx: StarsOrderMenuContext) -> Menu:
        menu = Menu(finalizer=StripAndNavigationFinalizer())
        menu.header_text = '🌟 <b>Заказ <a href="https://funpay.com/orders/{order_id}/">{order_id}</a></b>'.format(
            order_id=ctx.stars_order.order_id,
        )
        menu.main_text = (
            '<blockquote><b>{message}</b></blockquote>\n\n'
            '🤠 <b><i>Покупатель: {buyer}</i></b>\n'
            '✨ <b><i>Кол-во: {stars_amount}</i></b>\n'
            '👤 <b><i>Telegram: @{telegram_username}</i></b>\n'
            '📍 <b><i>Статус: {status}</i></b>\n'
        ).format(
            message=html.escape(ctx.stars_order.message_obj.text),
            buyer=ctx.stars_order.order_preview.counterparty.username,
            stars_amount=ctx.stars_order.stars_amount,
            telegram_username=html.escape(ctx.stars_order.telegram_username),
            status=_STATUSES.get(ctx.stars_order.status, ctx.stars_order.status.name),
        )
        if ctx.stars_order.status == StarsOrderStatus.ERROR and ctx.stars_order.error is not None:
            menu.main_text += _ERRORS[ctx.stars_order.error] + '\n'

        menu.main_text += '\n'
        if ctx.stars_order.recipient_id:
            menu.main_text += (
                '🪪 <b><i>Recipient ID:</i></b> <code>{recipient_id}</code>\n'.format(
                    recipient_id=ctx.stars_order.recipient_id,
                )
            )

        if ctx.stars_order.fragment_request_id:
            menu.main_text += (
                '🗃️ <b><i>Fragment Request ID:</i></b> <code>{fragment_request_id}</code>\n'.format(
                    fragment_request_id=ctx.stars_order.fragment_request_id,
                )
            )

        if ctx.stars_order.status is StarsOrderStatus.DONE and ctx.stars_order.ton_transaction_id:
            menu.main_text += '#️⃣ <b><i>Hash транзакции:</i></b> <code>{hash}</code>\n'.format(
                hash=ctx.stars_order.ton_transaction_id,
            )

        menu.main_text = menu.main_text.strip()
        return menu
