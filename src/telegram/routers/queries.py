from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from autostars.src.telegram import callbacks as cbs
from autostars.src.types.enums import StarsOrderStatus
from autostars.src.autostars_provider import AutostarsProvider
from autostars.src.telegram.callbacks import ListOldOrders
from autostars.src.telegram.ui.context import OldOrdersMenuContext, OldOrdersListMenuContext

from funpayhub.lib.translater import translater

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery as Query

    from funpayhub.lib.telegram.ui import UIRegistry as UI
    from funpayhub.app.main import FunPayHub as FPH


router = Router(name='autostars:queries')
ru = translater.translate


@router.callback_query(cbs.CheckOldOrders.filter())
async def check_old_orders(q: Query, autostars_provider: AutostarsProvider, hub: FPH):
    orders = await autostars_provider.storage.get_old_orders(hub.instance_id)
    if not orders:
        return q.answer(ru('✅ Нет незаконченных заказов с прошлых запусков.'), show_alert=True)

    await OldOrdersMenuContext(
        menu_id='autostars:old_orders_notification',
        trigger=q,
        errored_orders=len(orders.get(StarsOrderStatus.ERROR, [])),
        waiting_username_orders=len(orders.get(StarsOrderStatus.WAITING_FOR_USERNAME, [])),
        ready_orders=len(orders.get(StarsOrderStatus.READY, [])),
        unprocessed_orders=len(orders.get(StarsOrderStatus.UNPROCESSED, [])),
    ).apply_to()


@router.callback_query(cbs.ListOldOrders.filter())
async def list_old_orders(
    q: Query,
    tg_ui: UI,
    autostars_provider: AutostarsProvider,
    hub: FPH,
    cbd: ListOldOrders,
):
    orders = await autostars_provider.storage.get_old_orders(hub.instance_id)
    if not orders.get(cbd.status, []):
        return q.answer(
            ru(
                '✅ Нет заказов с прошлых запусков со статусом {status}.',
                status=ru(cbd.status.desc).lower(),
            ),
            show_alert=True,
        )

    await OldOrdersListMenuContext(
        menu_id='autostars:old_orders_list',
        trigger=q,
        orders_status=cbd.status,
        orders=orders[cbd.status],
    ).apply_to()


@router.callback_query(cbs.OldOrdersAction.filter())
async def old_orders_action(
    q: Query,
    callback_data: cbs.OldOrdersAction,
    autostars_provider: AutostarsProvider,
    hub: FPH,
):
    orders_dict = await autostars_provider.storage.get_old_orders(hub.instance_id)
    orders = orders_dict.get(callback_data.status, [])
    if not orders:
        return q.answer(
            ru(
                '✅ Нет заказов с прошлого запуска со статусом "{status}".',
                status=ru(callback_data.status.desc).lower(),
            ),
            show_alert=True,
        )

    if callback_data.action == 'dont_ignore':
        for i in orders:
            i.hub_instance = hub.instance_id
        await autostars_provider.storage.add_or_update_orders(*orders)
        msg = ru(
            '✅ Все заказы с прошлых запусков со статусом "{status}" будут выполнены '
            'в ближайшее время.',
            status=ru(callback_data.status.desc).lower(),
        )
    elif callback_data.action == 'mark_done':
        for i in orders:
            i.status = StarsOrderStatus.FORCE_DONE
        await autostars_provider.storage.add_or_update_orders(*orders)
        msg = ru(
            '✅ Все заказы с прошлых запусков со статусом "{status}" помечены как выполненные.',
            status=ru(callback_data.status.desc).lower(),
        )
    elif callback_data.action == 'mark_refunded':
        for i in orders:
            i.status = StarsOrderStatus.FORCE_REFUNDED
        await autostars_provider.storage.add_or_update_orders(*orders)
        msg = ru(
            '✅ Все заказы с прошлых запусков со статусом "{status}" помечены как возвращенные.',
            status=ru(callback_data.status.desc).lower(),
        )
    elif callback_data.action == 'delete':
        await autostars_provider.storage.delete_orders(*(i.order_id for i in orders))
        msg = ru(
            '🗑️ Все заказы с прошлых запусков со статусом "{status}" удалены.',
            status=ru(callback_data.status.desc).lower(),
        )
    else:
        msg = ru('❌ Неизвестное действие.')

    await q.answer(msg, show_alert=True)
