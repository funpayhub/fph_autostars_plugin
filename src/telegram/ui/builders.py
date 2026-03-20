from __future__ import annotations

import html
import math
from functools import reduce
from typing import TYPE_CHECKING

from autostars.src.types.enums import (
    StarsOrderStatus,
    StarsOrderStatus as SOS,
)
from autostars.src.telegram.callbacks import ListOldOrders, OldOrdersAction
from autostars.src.telegram.ui.context import (
    OldOrdersMenuContext,
    StarsOrderMenuContext,
    OldOrdersListMenuContext,
    OrdersListMenuContext
)

from funpayhub.lib.translater import translater
from funpayhub.lib.telegram.ui import Menu, MenuBuilder, MenuContext
from funpayhub.lib.base_app.telegram.app.ui.ui_finalizers import (
    StripAndNavigationFinalizer,
    build_view_navigation_btns,
)

from funpayhub.app.telegram.ui.premade import confirmable_button


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder
    from autostars.src.autostars_provider import AutostarsProvider
    from autostars.src.transferer_service import TransferrerService
    from funpayhub.app.main import FunPayHub as FPH


ru = translater.translate


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
        menu.main_text = ru(
            '<blockquote><b>{message}</b></blockquote>\n\n'
            '🤠 <b><i>Покупатель: {buyer}</i></b>\n'
            '✨ <b><i>Кол-во: {stars_amount}</i></b>\n'
            '👤 <b><i>Telegram: @{telegram_username}</i></b>\n'
            '🐙 <b><i>FunPay Hub ID:</i></b> <code>{hub_instance}</code>\n'
            '♻️ <b><i>Осталось попыток: {attempts}</i></b>\n'
            '📍 <b><i>Статус: {status}</i></b>\n',
            message=html.escape(ctx.stars_order.message_obj.text),
            buyer=ctx.stars_order.order_preview.counterparty.username,
            stars_amount=ctx.stars_order.stars_amount,
            telegram_username=html.escape(ctx.stars_order.telegram_username),
            status=ctx.stars_order.status.desc,
            hub_instance=ctx.stars_order.hub_instance,
            attempts=ctx.stars_order.retries_left,
        )

        if ctx.stars_order.error is not None:
            menu.main_text += f'<b><i>❌ Последняя ошибка: {ctx.stars_order.error.desc}</i></b>\n'

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
                    hash=ctx.stars_order.in_msg_hash,
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
    context_type=MenuContext,
):
    async def build(
        self,
        ctx: MenuContext,
        autostars_provider: AutostarsProvider,
        autostars_service: TransferrerService,
    ) -> Menu:
        menu = Menu(finalizer=StripAndNavigationFinalizer())

        if autostars_service._stopped.is_set():
            menu.main_text = '❌ <b>Статус сервиса: выключен.</b>\n'
        else:
            menu.main_text = '✅ <b>Статус сервиса: активен.</b>\n'

        if autostars_provider.wallet is not None:
            menu.main_text += (
                f'✅ <b>TON кошелек: <code>{autostars_provider.wallet.address}</code>.</b>\n'
            )
        else:
            menu.main_text += '❌ <b>TON кошелек: не подключен.</b>\n'

        if autostars_provider.fragment is not None:
            menu.main_text += '✅ <b>Fragment: подключен.</b>\n'
        else:
            menu.main_text += '❌ <b>Fragment: не подключен.</b>\n'

        return menu


class OldOrdersMenuBuilder(MenuBuilder, menu_id='autostars:old_orders', context_type=MenuContext):
    async def build(self, ctx: MenuContext, hub: FPH, autostars_provider: AutostarsProvider) -> Menu:
        menu = Menu(finalizer=StripAndNavigationFinalizer())
        old_orders = await autostars_provider.storage.get_old_orders(hub.instance_id)

        if not old_orders:
            menu.main_text = ru(
                '<b>✅Нет незавершенных заказов с предыдущих запусков FunPay Hub.</b>'
            )
            return menu

        total_len = reduce(lambda x, y: x + len(y), old_orders.values())
        menu.main_text = ru(
            '<b>⚠️ Обнаружены заказы (<code>{orders_amount}</code>), которые были инициированы во время'
            ' предыдущего запуска FunPayHub, но так и не были завершены.</b>\n\n',
            orders_amount=total_len,
        )

        if old_orders.get(StarsOrderStatus.UNPROCESSED):
            menu.main_text += ru(
                '<b>🔘 Необработанные заказы (<code>{orders_amount}</code>)</b> были сохранены '
                'в базу данных, но для них даже не была выполнена проверка Telegram юзернейма.\n\n',
                orders_amount=len(old_orders[StarsOrderStatus.UNPROCESSED]),
            )
            menu.main_keyboard.add_callback_button(
                button_id='open_unprocessed_orders',
                text=ru('🔘 Необработанные заказы'),
                callback_data=ListOldOrders(
                    status=StarsOrderStatus.UNPROCESSED,
                    ui_history=ctx.as_ui_history(),
                ).pack(),
            )

        if old_orders.get(StarsOrderStatus.WAITING_FOR_USERNAME):
            menu.main_text += ru(
                '<b>⏳ Заказы, ожидающие ввод валидного Telegram юзернейма (<code>{orders_amount}</code>),</b> '
                'были созданы, но юзернеймы, которые передали покупатели, либо невалидны, '
                'либо не были найдены.\n\n',
                orders_amount=len(old_orders[StarsOrderStatus.WAITING_FOR_USERNAME]),
            )
            menu.main_keyboard.add_callback_button(
                button_id='open_waiting_username_orders',
                text=ru('⏳ Ожидающие юзернейм'),
                callback_data=ListOldOrders(
                    status=StarsOrderStatus.WAITING_FOR_USERNAME,
                    ui_history=ctx.as_ui_history(),
                ).pack(),
            )

        if old_orders.get(StarsOrderStatus.READY):
            menu.main_text += ru(
                '<b>⚡ Заказы, готовые к выполнению (<code>{orders_amount}</code>)</b>, '
                'полностью валидны, но до них так и не дошла очередь.\n\n',
                orders_amount=len(old_orders[StarsOrderStatus.READY]),
            )
            menu.main_keyboard.add_callback_button(
                button_id='open_ready_orders',
                text=ru('⚡ Готовые к выполнению'),
                callback_data=ListOldOrders(
                    status=StarsOrderStatus.READY,
                    ui_history=ctx.as_ui_history(),
                ).pack(),
            )

        if old_orders.get(StarsOrderStatus.ERROR):
            menu.main_text += ru(
                '<b>⁉️ Заказы, по которым не удалось выполнить транзакцию '
                '(<code>{orders_amount}</code>)</b>, но у них есть еще несколько попыток.\n\n',
                orders_amount=len(old_orders[StarsOrderStatus.ERROR]),
            )
            menu.main_keyboard.add_callback_button(
                button_id='open_errored_orders',
                text=ru('⁉️ Заказы с ошибкой'),
                callback_data=ListOldOrders(
                    status=StarsOrderStatus.ERROR,
                    ui_history=ctx.as_ui_history(),
                ).pack(),
            )

        menu.main_text += ru(
            '🛠️ Выберите, что делать с заказами.\n'
            'Вы можете ничего с ними не делать, но тогда плагин будет их игнорировать, '
            'а это уведомление появится снова при следующем запуске.',
        )

        return menu


class OldOrdersListMenuBuilder(
    MenuBuilder,
    menu_id='autostars:old_orders_list',
    context_type=OldOrdersListMenuContext,
):
    async def build(self, ctx: OldOrdersListMenuContext) -> Menu:
        menu = Menu(finalizer=StripAndNavigationFinalizer())

        menu.header_text = ru(
            '<b>Список заказов с прошлого запуска со статусом <i><u>{status}</u></i></b>.',
            status=ru(ctx.orders_status.desc).lower(),
        )

        orders = ctx.orders[ctx.view_page * 50 : ctx.view_page * 50 + 50]
        menu.header_keyboard = await build_view_navigation_btns(
            ctx,
            math.ceil(len(ctx.orders) / 50),
        )

        menu.main_text = '\n'.join(self.gen_order_text(i) for i in orders)

        if orders:
            menu.footer_text = ru('🛠️ Выберите, что делать с заказами.')

            menu.main_keyboard.add_rows(
                confirmable_button(
                    ctx,
                    text='♻️ Не игнорировать',
                    button_id='dont_ignore',
                    callback_data=OldOrdersAction(
                        status=ctx.orders_status,
                        action='dont_ignore',
                        ui_history=ctx.as_ui_history()
                    ).pack(),
                ),
                confirmable_button(
                    ctx,
                    text='✅ Пометить как выполненные',
                    button_id='mark_done',
                    callback_data=OldOrdersAction(
                        status=ctx.orders_status,
                        action='mark_done',
                        ui_history=ctx.as_ui_history(),
                    ).pack(),
                ),
                confirmable_button(
                    ctx,
                    text='💸 Пометить как возвращенные',
                    button_id='mark_refunded',
                    callback_data=OldOrdersAction(
                        status=ctx.orders_status,
                        action='mark_refunded',
                        ui_history=ctx.as_ui_history(),
                    ).pack(),
                ),
                confirmable_button(
                    ctx,
                    text='🗑️ Удалить',
                    button_id='delete',
                    callback_data=OldOrdersAction(
                        status=ctx.orders_status,
                        action='delete',
                        ui_history=ctx.as_ui_history(),
                    ).pack(),
                    style='danger',
                ),
            )

        return menu

    def gen_order_text(self, order: StarsOrder):
        return ru(
            '<b><a href="https://funpay.com/orders/{order_id}/">{order_id}</a> | '
            '{stars_amount} ⭐ | {funpay_username} (@{telegram_username})</b>',
            order_id=order.order_id,
            stars_amount=order.stars_amount,
            funpay_username=order.order_preview.counterparty.username,
            telegram_username=order.telegram_username,
        )


class OrdersListMenuBuilder(
    MenuBuilder,
    menu_id='autostars:orders_list',
    context_type=OrdersListMenuContext,
):
    async def build(self, ctx: OrdersListMenuContext) -> Menu:
        menu = Menu(finalizer=StripAndNavigationFinalizer())
        menu.header_text = ctx.header_text

        orders = ctx.orders[ctx.view_page * 25 : ctx.view_page * 25 + 25]
        menu.header_keyboard = await build_view_navigation_btns(
            ctx,
            math.ceil(len(ctx.orders) / 25),
        )
        menu.main_text = '\n'.join(self.gen_order_text(i) for i in orders)
        return menu

    def gen_order_text(self, order: StarsOrder):
        if order.status is not StarsOrderStatus.ERROR:
            text = ru(
                '<b><a href="https://funpay.com/orders/{order_id}/">{order_id}</a> | '
                '{stars_amount} ⭐ | {funpay_username} (@{telegram_username})</b>',
                order_id=order.order_id,
                stars_amount=order.stars_amount,
                funpay_username=order.order_preview.counterparty.username,
                telegram_username=order.telegram_username,
            )
        else:
            text = ru(
                '<b><a href="https://funpay.com/orders/{order_id}/">{order_id}</a> | '
                '{stars_amount} ⭐ | {funpay_username} (@{telegram_username})\n{error}</b>\n',
                order_id=order.order_id,
                stars_amount=order.stars_amount,
                funpay_username=order.order_preview.counterparty.username,
                telegram_username=order.telegram_username,
                error=ru(order.error.desc) if order.error else 'no error'
            )

        return text