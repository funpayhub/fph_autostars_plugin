from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from autostars.src.types.enums import StarsOrderStatus
from autostars.src.telegram.ui.context import StarsOrderMenuContext

from funpayhub.lib.base_app.telegram.utils import delete_message

from funpayhub.app.telegram.ui.ids import MenuIds
from funpayhub.app.telegram.ui.builders.context import StateUIContext

from . import states


if TYPE_CHECKING:
    from aiogram.types import Message
    from autostars.src.storage import Storage

    from funpayhub.lib.translater import Translater
    from funpayhub.lib.telegram.ui import UIRegistry


router = Router(name='autostars')


async def _show_order_info(order_id: str, message: Message, storage: Storage, tg_ui: UIRegistry):
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
async def autostars_offer_info(
    message: Message, autostars_storage: Storage, tg_ui: UIRegistry, state: FSMContext
):
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
    await _show_order_info(order_id, message, autostars_storage, tg_ui)


@router.message(states.ViewingOrderInfo.filter(), lambda message: message.text)
async def autostars_offer_info_from_state(
    message: Message, autostars_storage: Storage, tg_ui: UIRegistry, state: FSMContext
):
    obj = await states.ViewingOrderInfo.get(state)
    await states.ViewingOrderInfo.clear(state)
    await _show_order_info(message.text, message, autostars_storage, tg_ui)
    delete_message(obj.state_message)


async def _mark_as_done(order_ids: set[str], storage: Storage, translater: Translater) -> str:
    orders = await storage.get_orders(*order_ids)

    done = set()
    for order in orders.values():
        order.status = StarsOrderStatus.DONE
        done.add(order.order_id)

    await storage.add_or_update_orders(*orders.values())
    not_found = order_ids - done
    text = ''
    if done:
        text += translater.translate(
            '<b>✅ Заказы {orders} помечены как выполненные.</b>\n\n',
        ).format(orders=', '.join(f'<code>{i}</code>' for i in done))

    if not_found:
        text += translater.translate('<b>⚠️ Не удалось найти заказы {orders}.</b>').format(
            orders=', '.join(f'<code>{i}</code>' for i in not_found),
        )
    return text


@router.message(Command('stars_mark_done'))
async def mark_as_ready(
    message: Message,
    autostars_storage: Storage,
    translater: Translater,
    state: FSMContext,
    tg_ui: UIRegistry,
):
    args = message.text.split(' ')[1:]
    if not args:
        msg = await StateUIContext(
            menu_id=MenuIds.state_menu,
            trigger=message,
            text='<b>❓ Укажите ID одного и более заказов (через пробел).</b>',
        ).build_and_answer(tg_ui, message)
        await states.MarkingAsDoneState(state_message=msg).set(state)
        return

    order_ids = set(args)
    text = await _mark_as_done(order_ids, autostars_storage, translater)

    await message.answer(text.strip())


@router.message(states.MarkingAsDoneState.filter(), lambda message: message.text)
async def mark_as_done_from_state(
    message: Message,
    autostars_storage: Storage,
    translater: Translater,
    state: FSMContext,
):
    obj = await states.MarkingAsDoneState.get(state)
    await states.MarkingAsDoneState.clear(state)
    order_ids = set(message.text.split(' '))
    text = await _mark_as_done(order_ids, autostars_storage, translater)
    await message.answer(text.strip())
    delete_message(obj.state_message)
