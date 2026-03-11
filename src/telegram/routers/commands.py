from __future__ import annotations

import re
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command
from autostars.src.telegram import (
    states,
    callbacks as cbs,
)
from autostars.src.types.enums import StarsOrderStatus
from autostars.src.autostars_provider import AutostarsProvider
from autostars.src.telegram.ui.context import OldOrdersMenuContext, StarsOrderMenuContext

from funpayhub.lib.translater import translater
from funpayhub.lib.telegram.ui import MenuContext
from funpayhub.lib.base_app.telegram.utils import delete_message

from funpayhub.app.main import FunPayHub
from funpayhub.app.telegram.ui.ids import MenuIds
from funpayhub.app.telegram.ui.builders.context import StateUIContext


if TYPE_CHECKING:
    from aiogram.types import Message
    from autostars.src.storage import Storage
    from funpayhub.lib.telegram.ui import UIRegistry as UI
    from aiogram.fsm.context import FSM


router = Router(name='autostars')
ru = translater.translate
ORDERS_SEP_RE = re.compile('[,;\s]+')


async def _show_order_info_helper(order_id: str, message: Message, storage: Storage, tg_ui: UI):
    order = await storage.get_order(order_id)
    if order is None:
        await message.answer('❌ <b>Заказ {order_id} не найден.</b>'.format(order_id=order_id))
        return

    await StarsOrderMenuContext(
        menu_id='autostars:stars_order_info',
        trigger=message,
        stars_order=order,
    ).build_and_answer(tg_ui, message)


@router.message(Command('stars_order_info'))
async def order_info(message: Message, autostars_storage: Storage, tg_ui: UI, state: FSM):
    args = message.text.split(' ')[1:]
    if not args:
        msg = await StateUIContext(
            menu_id=MenuIds.state_menu,
            trigger=message,
            text='<b>❓ Укажите ID заказа.</b>',
        ).build_and_answer(tg_ui, message)
        await states.ViewingOrderInfo(state_message=msg).set(state)
        return

    order_id = args[0]
    await _show_order_info_helper(order_id, message, autostars_storage, tg_ui)


@router.message(states.ViewingOrderInfo.filter(), lambda message: message.text)
async def order_info2(message: Message, autostars_storage: Storage, tg_ui: UI, state: FSM):
    obj = await states.ViewingOrderInfo.get(state)
    await states.ViewingOrderInfo.clear(state)
    await _show_order_info_helper(message.text, message, autostars_storage, tg_ui)
    delete_message(obj.state_message)


@router.message(Command('stars_old_orders'))
async def list_old_orders(message: Message, tg_ui: UI, autostars_provider: AutostarsProvider, hub: FunPayHub):
    orders = await autostars_provider.storage.get_old_orders(hub.instance_id)
    if not orders:
        await message.answer(
            ru('<b>✅ Нет незаконченных заказов с прошлых запусков.</b>'),
        )
        return

    await OldOrdersMenuContext(
        menu_id='autostars:old_orders_notification',
        trigger=message,
        errored_orders=len(orders.get(StarsOrderStatus.ERROR, [])),
        waiting_username_orders=len(orders.get(StarsOrderStatus.WAITING_FOR_USERNAME, [])),
        ready_orders=len(orders.get(StarsOrderStatus.READY, [])),
        unprocessed_orders=len(orders.get(StarsOrderStatus.UNPROCESSED, [])),
        callback_override=cbs.CheckOldOrders(),
    ).build_and_answer(tg_ui, message)


@router.message(Command('stars_status'))
async def stars_status(message: Message, tg_ui: UI):
    await MenuContext(menu_id='autostars:status', trigger=message).build_and_answer(tg_ui, message)


# -----------------------------------------------------
# ------------------ Mark-as Commands -----------------
# -----------------------------------------------------
actions = {
    states.Action.mark_done: {
        'status': StarsOrderStatus.FORCE_DONE,
        'done_text': '<b>✅ Заказы {orders} помечены как выполненные.</b>',
        'not_found_text': '<b>⚠️ Не удалось найти заказы {orders}.</b>'
    },
    states.Action.mark_refunded: {
        'status': StarsOrderStatus.FORCE_REFUNDED,
        'done_text': '<b>✅ Заказы {orders} помечены как возвращенные.</b>',
        'not_found_text': '<b>⚠️ Не удалось найти заказы {orders}.</b>'
    },
    states.Action.dont_ignore: {
        'done_text': '<b>✅ Заказы {orders} теперь не игнорируются плагином.</b>',
        'not_found_text': '<b>⚠️ Не удалось найти заказы {orders}.</b>',
        'instance_id': getattr(__builtins__, 'APP_INSTANCE_ID', 'EMPTY_INSTANCE')
    },
}

cmds = {
    'stars_mark_done': states.Action.mark_done,
    'stars_mark_refunded': states.Action.mark_refunded,
    'stars_dont_ignore': states.Action.dont_ignore,
}


def _extract_order_ids(arg: str) -> list[str]:
    seen = set()
    return [i for i in ORDERS_SEP_RE.split(arg) if i and not (i in seen or seen.add(i))]


async def _mark_orders(
    order_ids: list[str],
    storage: Storage,
    status: StarsOrderStatus | None = None,
    instance_id: str | None = None,
    done_text: str = '',
    not_found_text: str = '',
) -> str:
    orders = await storage.get_orders(*order_ids)
    done = []

    for order in orders.values():
        if status is not None:
            order.status = status
        if instance_id is not None:
            order.instance_id = instance_id
        done.append(order.order_id)

    await storage.add_or_update_orders(*orders.values())
    not_found = [i for i in order_ids if i not in done]

    text = ''
    if done:
        text += ru(done_text, orders=', '.join(f'<code>{i}</code>' for i in done)) + '\n\n'

    if not_found:
        text += ru(not_found_text, orders=', '.join(f'<code>{i}</code>' for i in not_found)) + '\n\n'
    return text.strip()


async def _set_state(
    message: Message,
    state: FSM,
    tg_ui: UI,
    action: states.Action,
    from_cmd: bool = True
) -> list[str] | None:
    args = message.text.split(' ', 1)[1:] if from_cmd else [message.text]
    order_ids = _extract_order_ids(args[0]) if args else []
    if order_ids:
        return order_ids

    msg = await StateUIContext(
        menu_id=MenuIds.state_menu,
        trigger=message,
        text=ru('<b>❓ Укажите ID одного и более заказов (через пробел или запятую).</b>')
    ).build_and_answer(tg_ui, message)
    await states.OrdersActionState(state_message=msg, action=action).set(state)
    return None


@router.message(Command('stars_mark_done'))
@router.message(Command('stars_mark_refunded'))
@router.message(Command('stars_dont_ignore'))
async def mark_done(message: Message, autostars_storage: Storage, state: FSM, tg_ui: UI, command: str):
    if not (ids := await _set_state(message, state, tg_ui, cmds[command])):
        return

    text = await _mark_orders(ids, autostars_storage, **actions[cmds[command]])
    await message.answer(text)


@router.message(Command('stars_delete'))
async def delete(message: Message, autostars_storage: Storage, state: FSM, tg_ui: UI):
    if not (ids := await _set_state(message, state, tg_ui, states.Action.dont_ignore)):
        return

    await autostars_storage.delete_orders(*ids)
    await message.answer(ru('<b>🗑️ Заказы {orders} удалены.</b>', orders=ids))


@router.message(states.OrdersActionState.filter(), lambda message: message.text)
async def do_orders_action(message: Message, autostars_storage: Storage, state: FSM, tg_ui: UI):
    obj = await states.OrdersActionState.get(state)
    await states.OrdersActionState.clear(state)

    order_ids = await _set_state(message, state, tg_ui, obj.action, from_cmd=False)
    if not order_ids:
        delete_message(obj.state_message)
        return

    if obj.action in (states.Action.mark_done, states.Action.mark_refunded, states.Action.dont_ignore):
        text = await _mark_orders(order_ids, autostars_storage, **actions[obj.action])
    elif obj.action is states.Action.delete:
        await autostars_storage.delete_orders(*order_ids)
        text = ru('<b>🗑️ Заказы {orders} удалены.</b>', orders=order_ids)
    else:
        text = ru('❌ Неизвестное действие. Отправьте это сообщение разработчику.')

    await message.answer(text)
    delete_message(obj.state_message)
