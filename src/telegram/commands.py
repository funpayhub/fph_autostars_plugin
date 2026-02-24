from __future__ import annotations

from typing import TYPE_CHECKING
from aiogram import Router
from aiogram.filters import Command
from autostars.src.telegram.ui.context import StarsOrderMenuContext


if TYPE_CHECKING:
    from aiogram.types import Message
    from autostars.src.storage import Storage
    from funpayhub.lib.telegram.ui import UIRegistry


router = Router(name='autostars')


@router.message(Command('autostars_order_info'))
async def autostars_offer_info(message: Message, autostars_storage: Storage, tg_ui: UIRegistry):
    args = message.text.split(' ')[1:]
    if not args:
        await message.answer('<b>❌ Неверное использование команды.\n/autostars_order_info &lt;ORDERID&gt;</b>')
        return

    order_id = args[0]
    order = await autostars_storage.get_order(order_id)
    if order is None:
        await message.answer('❌ <b>Заказ {order_id} не найден.</b>'.format(order_id=order_id))
        return

    await StarsOrderMenuContext(
        menu_id='autostars:stars_order_info',
        trigger=message,
        stars_order=order,
    ).build_and_answer(tg_ui, message)
