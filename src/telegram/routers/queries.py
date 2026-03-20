from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from autostars.src.telegram import callbacks as cbs
from autostars.src.types.enums import StarsOrderStatus
from autostars.src.autostars_provider import AutostarsProvider
from autostars.src.telegram.callbacks import ListOldOrders
from autostars.src.telegram.ui.context import OldOrdersListMenuContext
from funpayhub.lib.telegram.ui import UIRegistry
from funpayhub.lib.translater import translater

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery as Query
    from funpayhub.app.main import FunPayHub as FPH


router = Router(name='autostars:queries')
ru = translater.translate


@router.callback_query(cbs.ListOldOrders.filter())
async def list_old_orders(q: Query, cbd: ListOldOrders):
    await OldOrdersListMenuContext(
        menu_id='autostars:old_orders_list', trigger=q, orders_status=cbd.status
    ).apply_to()


@router.callback_query(cbs.OldOrdersAction.filter())
async def old_orders_action(
    q: Query,
    cbd: cbs.OldOrdersAction,
    autostars_provider: AutostarsProvider,
    hub: FPH,
    tg_ui: UIRegistry
):
    orders_dict = await autostars_provider.storage.get_old_orders(hub.instance_id)
    orders = orders_dict.get(cbd.status, [])
    st = translater.translate(cbd.status.desc).lower()
    if not orders:
        return q.answer(ru('✅ Нет старых заказов со статусом "{s}".', s=st), show_alert=True)

    messages = {
        'dont_ignore': ru('✅ Заказы со статусом "{s}" теперь не игнорируются.', s=st),
        'mark_done': ru('✅ Заказы со статусом "{s}" помечены как выполненные.', s=st),
        'mark_refunded': ru('✅ Заказы со статусом "{status}" помечены как возвращенные.', s=st),
        'delete': ru('🗑️ Старые заказы со статусом "{status}" удалены.', s=st)
    }
    msg = messages.get(cbd.action, ru('Действие выполнено но разраб забыл добавить сообщение ._.'))

    actions = {
        'dont_ignore': lambda o: setattr(o, 'hub_instance', hub.instance_id),
        'mark_done': lambda o: setattr(o, 'status', StarsOrderStatus.FORCE_DONE),
        'mark_refunded': lambda o: setattr(o, 'status', StarsOrderStatus.FORCE_REFUNDED),
    }

    if cbd.action in actions:
        for i in orders:
            actions[cbd.action](i)
        await autostars_provider.storage.add_or_update_orders(*orders)
    elif cbd.action == 'delete':
        await autostars_provider.storage.delete_orders(*(i.order_id for i in orders))
    else:
        return q.answer(ru('❌ Неизвестное действие.'))

    await q.answer(msg, show_alert=True)
    await tg_ui.context_from_history(cbd.ui_history, trigger=q).apply_to()
