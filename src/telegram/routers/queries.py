from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router

from autostars.src.telegram.callbacks import ListOldOrders
from autostars.src.types.enums import StarsOrderStatus
from autostars.src.autostars_provider import AutostarsProvider
from autostars.src.telegram.ui.context import OldOrdersMenuContext, OldOrdersListMenuContext

from funpayhub.lib.translater import translater

from funpayhub.app.main import FunPayHub
from autostars.src.telegram import callbacks as cbs


if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from funpayhub.lib.telegram.ui import UIRegistry


router = Router(name='autostars:queries')
ru = translater.translate


@router.callback_query(cbs.CheckOldOrders.filter())
async def check_old_orders(
    query: CallbackQuery,
    tg_ui: UIRegistry,
    autostars_provider: AutostarsProvider,
    hub: FunPayHub,
):
    orders = await autostars_provider.storage.get_old_orders(hub.instance_id)
    if not orders:
        await query.answer(
            ru('✅ Нет незаконченных заказов с прошлых запусков.'),
            show_alert=True,
        )
        return

    await OldOrdersMenuContext(
        menu_id='autostars:old_orders_notification',
        trigger=query,
        errored_orders=len(orders[StarsOrderStatus.ERROR]),
        waiting_username_orders=len(orders[StarsOrderStatus.WAITING_FOR_USERNAME]),
        ready_orders=len(orders[StarsOrderStatus.READY]),
        unprocessed_orders=len(orders[StarsOrderStatus.UNPROCESSED]),
        callback_override=cbs.CheckOldOrders()
    ).build_and_apply(tg_ui, query.message)


@router.callback_query(cbs.ListOldOrders.filter())
async def list_old_orders(
    query: CallbackQuery,
    tg_ui: UIRegistry,
    autostars_provider: AutostarsProvider,
    hub: FunPayHub,
    callback_data: ListOldOrders
):
    orders = await autostars_provider.storage.get_old_orders(hub.instance_id)
    if not orders[callback_data.status]:
        await query.answer(
            ru(
                '✅ Нет заказов с прошлых запусков со статусом {status}.',
                status=ru(callback_data.status.desc).lower()
            ),
            show_alert=True
        )
        return

    await OldOrdersListMenuContext(
        menu_id='autostars:old_orders_list',
        trigger=query,
        orders_status=callback_data.status,
        orders=orders[callback_data.status],
    ).build_and_apply(tg_ui, query.message)


@router.callback_query(cbs.OldOrdersAction.filter())
async def old_orders_action(
    query: CallbackQuery,
    callback_data: cbs.OldOrdersAction,
    autostars_provider: AutostarsProvider,
    hub: FunPayHub
):
    orders_dict = await autostars_provider.storage.get_old_orders(hub.instance_id)
    orders = orders_dict[callback_data.status]
    if not orders:
        await query.answer(
            ru(
                '✅ Нет заказов с прошлого запуска со статусом \"{status}\".',
                status=ru(callback_data.status.desc).lower()
            ),
            show_alert=True
        )
        return

    if callback_data.action == 'dont_ignore':
        for i in orders:
            i.hub_instance = hub.instance_id
        await autostars_provider.storage.add_or_update_orders(*orders)
        msg = ru(
            '✅ Все заказы с прошлых запусков со статусом \"{status}\" будут выполнены '
            'в ближайшее время.',
            status=ru(callback_data.status.desc).lower()
        )
    elif callback_data.action == 'mark_done':
        for i in orders:
            i.status = StarsOrderStatus.FORCE_DONE
        await autostars_provider.storage.add_or_update_orders(*orders)
        msg = ru(
            '✅ Все заказы с прошлых запусков со статусом \"{status}\" помечены как выполненные.',
            status=ru(callback_data.status.desc).lower()
        )
    elif callback_data.action == 'mark_refunded':
        for i in orders:
            i.status = StarsOrderStatus.FORCE_REFUNDED
        await autostars_provider.storage.add_or_update_orders(*orders)
        msg = ru(
            '✅ Все заказы с прошлых запусков со статусом \"{status}\" помечены как возвращенные.',
            status=ru(callback_data.status.desc).lower()
        )
    elif callback_data.action == 'delete':
        await autostars_provider.storage.delete_orders(*(i.order_id for i in orders))
        msg = ru(
            '🗑️ Все заказы с прошлых запусков со статусом \"{status}\" удалены.',
            status=ru(callback_data.status.desc).lower()
        )
    else:
        msg = ru('❌ Неизвестное действие.')

    await query.answer(msg, show_alert=True)