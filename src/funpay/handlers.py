from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from itertools import chain

from funpaybotengine import Router
from funpaybotengine.types.enums import SubcategoryType

from funpayhub.lib.translater import _ru

from ..exceptions import FragmentResponseError
from ..formatters import StarsOrderFormatterContext, StarsOrderCategory
from funpayhub.app.formatters import GeneralFormattersCategory
from ..types.enums import ErrorTypes, StarsOrderStatus
from funpayhub.lib.hub.text_formatters.category import InCategory


if TYPE_CHECKING:
    from funpaybotengine.runner import EventsStack

    from funpayhub.lib.plugin import LoadedPlugin
    from funpayhub.lib.translater import Translater as Tr

    from funpayhub.app.main import FunPayHub as FPH

    from ..types import StarsOrder
    from ..plugin import AutostarsPlugin
    from ..storage import Storage
    from ..fragment_api import FragmentAPIProvider as FragmentAPI
    from ..properties import AutostarsProperties


from .utils import extract_stars_orders


router = Router(name='autostars')


TELEGRAM_CATEGORY_ID = 224
STARS_SUBCATEGORY_ID = 2418


async def check_usernames(
    orders: list[StarsOrder],
    storage: Storage,
    api: FragmentAPI,
    plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties]
):
    invalid_username: list[StarsOrder] = []
    ready: list[StarsOrder] = []

    async def check_username(order: StarsOrder) -> None:
        for _ in range(3):
            try:
                r = await api.api.search_stars_recipient(order.telegram_username)
                order.status = StarsOrderStatus.READY
                order.recipient_id = r.found.recipient
                ready.append(order)
                return
            except FragmentResponseError:
                order.status = StarsOrderStatus.WAITING_FOR_USERNAME
                invalid_username.append(order)
                asyncio.create_task(on_username_not_found(order, plugin))
                return
            except Exception:
                await asyncio.sleep(1)
        order.status = StarsOrderStatus.ERROR
        order.error = ErrorTypes.UNABLE_TO_FETCH_USERNAME
        order.retries_left = 0
        invalid_username.append(order)

    tasks = []
    for order in orders:
        if not order.telegram_username:
            order.status = StarsOrderStatus.WAITING_FOR_USERNAME
            invalid_username.append(order)

        if api.api is None:
            order.status = StarsOrderStatus.ERROR
            order.error = ErrorTypes.UNABLE_TO_FETCH_USERNAME
            invalid_username.append(order)
            continue

        tasks.append(
            asyncio.create_task(
                check_username(order),
                name=f'Autostars username check: {order.order_id} | {order.telegram_username}',
            ),
        )

    await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
    await storage.add_or_update_orders(*chain(invalid_username, ready))

    # todo: send notification to funpay
    # todo: send notification in chat if error occurred while fetching username


async def on_username_not_found(order: StarsOrder, plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties]) -> None:
    text = plugin.properties.messages.username_not_found_message.value
    if not text:
        return

    ctx = StarsOrderFormatterContext(
        new_message_event=order.sale_event.related_new_message_event,
        order_event=order.sale_event,
        goods_to_deliver=[],
        stars_order=order,
    )

    try:
        pack = await plugin.plugin.hub.funpay.text_formatters.format_text(
            text=text,
            context=ctx,
            query=InCategory(StarsOrderCategory).or_(InCategory(GeneralFormattersCategory))
        )
    except Exception:
        plugin.plugin.logger.error(
            _ru('Не удалось форматировать сообщение о неверном telegram юзернейме.'),
            exc_info=True
        )
        # todo: notification
        return

    try:
        await plugin.plugin.hub.funpay.send_messages_stack(pack, order.funpay_chat_id)
    except Exception:
        plugin.plugin.logger.error(
            _ru('Не удалось отправить сообщение о неверном telegram юзернейме.'),
            exc_info=True
        )
        # todo: notification
        return


@router.on_new_events_pack(
    lambda events_stack, hub: len(events_stack.events) > 1 and hub.funpay.authenticated,
    handler_id='Save telegram stars orders',
)
async def sale_orders(
    events_stack: EventsStack,
    hub: FPH,
    autostars_storage: Storage,
    plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties],
    translater: Tr,
    autostars_fragment_api: FragmentAPI,
) -> None:
    cat = await hub.funpay.bot.storage.get_category(TELEGRAM_CATEGORY_ID)
    subcat = [
        i
        for i in cat.subcategories
        if i.type == SubcategoryType.OFFERS and i.id == STARS_SUBCATEGORY_ID
    ][0]

    name = f'{cat.name}, {subcat.name}'
    stars_orders = await extract_stars_orders(events_stack.events, name, hub.instance_id)
    if not stars_orders:
        plugin.plugin.logger.debug(
            _ru('Нет событий о продаже связанных с Telegram stars. Events pack: %s.'),
            events_stack.id,
        )
        return

    plugin.plugin.logger.info(
        _ru('Добавляю данные о заказах %s в базу данных.'),
        [i.order_id for i in stars_orders],
    )

    errored: list[tuple[StarsOrder, Exception]] = []

    for i in stars_orders:
        try:
            await autostars_storage.add_or_update_order(i)
        except Exception as e:
            errored.append((i, e))
            plugin.plugin.logger.error(
                _ru('Не удалось добавить информацию о заказе %s в базу данных!'),
                i.order_id,
                exc_info=True,
            )

    if errored:
        hub.telegram.send_error_notification(
            translater.translate(
                '<b>Telegram Stars</b>\n<b>❌ CRITICAL ❌</b>\n\n'
                'Не удалось добавить информацию о заказах {order_ids} в базу данных!\n'
                'Плагин не будет знать об этих заказах и не сможет с ними ничего сделать. '
                'Эти заказы необходимо обработать вручную!',
            ).format(
                order_ids=', '.join(f'<code>{i[0].order_id}</code>' for i in errored),
            ),
        )
        return

    await check_usernames(stars_orders, autostars_storage, autostars_fragment_api, plugin)
