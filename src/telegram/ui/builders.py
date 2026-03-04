from __future__ import annotations

import html

from autostars.src.types.enums import StarsOrderStatus as SOS
from typing import TYPE_CHECKING

from funpayhub.lib.telegram.ui import Menu, MenuBuilder, MenuContext
from funpayhub.lib.base_app.telegram.app.ui.ui_finalizers import StripAndNavigationFinalizer

from autostars.src.telegram.ui.context import StarsOrderMenuContext

if TYPE_CHECKING:
    from autostars.src.autostars_provider import AutostarsProvider
    from autostars.src.transferer_service import TransferrerService


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
            '🐙 <b><i>FunPay Hub ID:</i></b> <code>{hub_instance}</code>\n'
            '♻️ <b><i>Осталось попыток: {attempts}</i></b>\n'
            '📍 <b><i>Статус: {status}</i></b>\n'
        ).format(
            message=html.escape(ctx.stars_order.message_obj.text),
            buyer=ctx.stars_order.order_preview.counterparty.username,
            stars_amount=ctx.stars_order.stars_amount,
            telegram_username=html.escape(ctx.stars_order.telegram_username),
            status=ctx.stars_order.status.desc,
            hub_instance=ctx.stars_order.hub_instance,
            attempts=ctx.stars_order.retries_left,
        )
        if ctx.stars_order.status in [SOS.ERROR, SOS.WAITING_FOR_USERNAME] and ctx.stars_order.error is not None:
            menu.main_text += f'<b><i>{ctx.stars_order.error.desc}</i></b>\n'

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

        if ctx.stars_order.in_msg_hash:
            menu.main_text += (
                '#️⃣ <b><i>Hash полезной нагрузки:</i></b> <code>{hash}</code>\n'.format(
                    hash=ctx.stars_order.in_msg_hash
                )
            )

        if ctx.stars_order.status is SOS.DONE and ctx.stars_order.transaction_hash:
            menu.main_text += '#️⃣ <b><i>Hash транзакции:</i></b> <code>{hash}</code>\n'.format(
                hash=ctx.stars_order.transaction_hash,
            )

            menu.header_keyboard.add_url_button(
                button_id='open_transasction',
                text='Открыть транзакцию',
                url=f'https://tonviewer.com/transaction/{ctx.stars_order.transaction_hash}',
            )

        menu.main_text = menu.main_text.strip()
        return menu


class StatusMenuBuilder(
    MenuBuilder,
    menu_id='autostars:status',
    context_type=MenuContext
):
    async def build(
        self,
        ctx: MenuContext,
        autostars_provider: AutostarsProvider,
        autostars_service: TransferrerService
    ) -> Menu:
        menu = Menu(finalizer=StripAndNavigationFinalizer())

        if autostars_service._stopped.is_set():
            menu.main_text = '❌ <b>Статус сервиса: выключен.</b>\n'
        else:
            menu.main_text = '✅ <b>Статус сервиса: активен.</b>\n'

        if autostars_provider.wallet is not None:
            menu.main_text += f'✅ <b>TON кошелек: <code>{autostars_provider.wallet.address}</code>.</b>\n'
        else:
            menu.main_text += '❌ <b>TON кошелек: не подключен.</b>\n'

        if autostars_provider.fragment is not None:
            menu.main_text += f'✅ <b>Fragment: подключен.</b>\n'
        else:
            menu.main_text += '❌ <b>Fragment: не подключен.</b>\n'

        return menu