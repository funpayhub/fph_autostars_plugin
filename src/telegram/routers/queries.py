from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from autostars.src.types.enums import StarsOrderStatus
from autostars.src.autostars_provider import AutostarsProvider
from autostars.src.telegram.ui.context import OldOrdersMenuContext

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
