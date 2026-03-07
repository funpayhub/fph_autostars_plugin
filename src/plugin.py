from __future__ import annotations

import asyncio
import logging
import traceback
from itertools import chain
from typing import TYPE_CHECKING

from pytoniq import LiteClient
from aiogram.types import BufferedInputFile
from aiogram.methods import SendDocument

from funpayhub.lib.base_app.telegram.app.ui.callbacks import OpenMenu
from funpayhub.lib.telegram import Command
from funpayhub.lib.properties import ListParameter
from funpayhub.lib.translater import _ru
import time

from funpayhub.app.plugin import Plugin

from .fph import router as fph_router
from .telegram.ui.context import OldOrdersMenuContext
from .ton import Wallet
from .other import NotificationChannels
from .funpay import funpay_router
from .tonapi import TonAPI
from .storage import Sqlite3Storage
from .telegram import ROUTERS
from .callbacks import Callbacks
from .formatters import FORMATTERS, StarsOrderCategory
from .properties import AutostarsProperties
from .telegram.ui import BUILDERS
from .fragment_api import FragmentAPI
from .autostars_provider import AutostarsProvider
from .transferer_service import TransferrerService
from .telegram.ui.modifications import MODIFICATIONS
from .types.enums import StarsOrderStatus as SOS, ErrorTypes
from collections import defaultdict

if TYPE_CHECKING:
    from aiogram import Router as TGRouter
    from funpaybotengine import Router as FPRouter

    from funpayhub.lib.properties import Properties
    from funpayhub.lib.telegram.ui import MenuBuilder, MenuModification
    from funpayhub.lib.hub.text_formatters import Formatter

    from funpayhub.app.dispatching import Router as HubRouter
    from .tonapi.types import Transaction
    from .types import StarsOrder


class AutostarsPlugin(Plugin):
    def __init__(self, *args):
        super().__init__(*args)

        self.api = TonAPI()
        self.provider: AutostarsProvider | None = None
        self.callbacks = Callbacks(self)

        self.props: AutostarsProperties | None = None
        self.transfer_service: TransferrerService | None = None

    async def setup_properties(self) -> None:
        self.hub.properties.telegram.notifications.attach_node(
            ListParameter(
                id=NotificationChannels.INFO,
                name='Autostars: общее',
                description='Общие уведомления плагина Autostars.',
            ),
        )

        self.hub.properties.telegram.notifications.attach_node(
            ListParameter(
                id=NotificationChannels.ERROR,
                name='Autostars: ошибки',
                description='Уведомления об ошибках в плагине Autostars.',
            ),
        )

    async def properties(self) -> Properties:
        self.props = AutostarsProperties()
        return self.props

    async def telegram_routers(self) -> TGRouter | list[TGRouter]:
        return ROUTERS

    async def funpay_routers(self) -> FPRouter | list[FPRouter]:
        return funpay_router

    async def hub_routers(self) -> HubRouter | list[HubRouter]:
        return fph_router

    async def commands(self) -> Command | list[Command] | None:
        return [
            Command(
                source=self.manifest.plugin_id,
                command='stars_order_info',
                description='[AutoStars] Информация о заказе.',
                setup=True,
            ),
            Command(
                source=self.manifest.plugin_id,
                command='stars_mark_done',
                description='[AutoStars] Пометить заказы как выполненные.',
                setup=True,
            ),
        ]

    async def formatters(self) -> type[Formatter] | list[type[Formatter]] | None:
        return FORMATTERS

    async def setup_formatters(self) -> None:
        self.hub.funpay.text_formatters.add_category(StarsOrderCategory)

    async def menus(self) -> type[MenuBuilder] | list[type[MenuBuilder]]:
        return BUILDERS

    async def menu_modifications(
        self,
    ) -> dict[str, type[MenuModification] | list[type[MenuModification]]]:
        return MODIFICATIONS

    async def post_setup(self) -> None:
        logger = logging.getLogger(LiteClient.__name__)
        logger.setLevel(logging.WARNING)

        storage = await Sqlite3Storage.from_path('storage/autostars.sqlite3')
        self.provider = AutostarsProvider(TonAPI(), storage)

        await self.check_old_transferring_orders()

        if self.props.wallet.cookies.value and self.props.wallet.fragment_hash.value:
            self.logger.info(_ru('Cookie и Hash найдены в настройках. Создаю FragmentAPI.'))
            self.provider._fragment = FragmentAPI(
                self.props.wallet.cookies.value,
                self.props.wallet.fragment_hash.value,
            )

        if self.props.wallet.mnemonics.value:
            self.logger.info(_ru('Мнемоники найдены в настройках. Создаю кошелек.'))
            try:
                self.provider._wallet = await Wallet.from_mnemonics(
                    self.props.wallet.mnemonics.value,
                    self.provider,
                )
                self.logger.info(_ru('Кошелек %s подключен.'), self.provider.wallet.address)
                self.hub.telegram.send_notification(
                    NotificationChannels.INFO,
                    self.hub.translater.translate(
                        '<b>✅ TON кошелек <code>{address}</code> подключен.\n\n'
                        '💰Баланс: <code>{balance}</code> TON</b>',
                    ).format(
                        address=self.provider.wallet.address,
                        balance=self.provider.wallet._last_info.balance / 1_000_000_000,
                    ),
                )

            except Exception:
                self.logger.error(_ru('Ошибка подключения к TON кошельку.'), exc_info=True)
                self.hub.telegram.send_notification(
                    NotificationChannels.ERROR,
                    self.hub.translater.translate(
                        '<b>[❌ CRITICAL ❌]\n'
                        'Не удалось подключиться к TON кошельку.\n\n'
                        'Подробности в логах.</b>',
                    ),
                )

        self.transfer_service = TransferrerService(self.provider, self.callbacks)

        self.hub.workflow_data.update(
            {
                'autostars_provider': self.provider,
                'autostars_callbacks': self.callbacks,
                'autostars_storage': self.provider.storage,
                'autostars_service': self.transfer_service,
            },
        )
        task = asyncio.create_task(self.transfer_service.main_loop())
        task.add_done_callback(self.service_done_callback)
        await self.check_old_orders()

    def service_done_callback(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.critical('Autostars service is dead.', exc_info=True)
            error_file = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            call = SendDocument(
                chat_id=0,
                caption=self.hub.translater.translate(
                    '<b>[❌ CRITICAL ❌]\n\n'
                    '☠️ Autostars сервис умер.\n'
                    '☠️ Переводы не будут совершаться.\n'
                    '☠️ Обязательно передайте это сообщение разработчику.\n'
                    '☠️ В данной ситуации поможет только перезапуск FunPay Hub.\n\n'
                    '☠️ Подробности в логах.</b>',
                ),
                document=BufferedInputFile(
                    error_file.encode(),
                    filename='autostars_service_crash_traceback.txt',
                ),
            )
            self.hub.telegram.send_notification_from_obj(NotificationChannels.ERROR, call)

    async def check_old_transferring_orders(self) -> None:
        orders_dict = await self.provider.storage.get_orders(
            instance_id=self.hub.instance_id,
            same_instance=False,
            status=SOS.TRANSFERRING,
        )
        orders = {i for i in orders_dict.values() if i.in_msg_hash}
        if not orders:
            return

        self.hub.telegram.send_notification(
            NotificationChannels.INFO,
            text=f'<b>⚠️ Найдены незавершенные транзакции с прошлого запуска FunPay Hub.\n'
                 f'Заказы: {", ".join(f"<code>{i.order_id}</code>" for i in orders)}.\n\n'
                 f'⌛ Выполняю проверку их статуса. Это может занять какое-то время (зависит от кол-ва заказов). '
                 f'Пока проверка не выполнится, сервис не будет запущен.</b>'
        )

        timeout = int(time.time() + 10)  # todo: valid_until from db
        done: dict[StarsOrder, Transaction] = {}
        for i in {i.in_msg_hash for i in orders}:
            try:
                tr = await self.provider.tonapi.wait_for_transfer(i, timeout)
                done.update({j: tr for j in orders if j.in_msg_hash == i})
            except TimeoutError:
                pass

        errored = {i for i in orders if i not in done}
        for order, trans in done.items():
            order.status = SOS.DONE
            order.error = None
            order.transaction_hash = trans.hash

        for order in errored:
            order.status = SOS.ERROR
            order.error = ErrorTypes.TRANSACTION_TIMEOUT_ERROR

        notification_parts = [f'✅ Проверка незавершенных транзакций завершена.']
        if done:
            notification_parts.append(
                f'✅ Подтверждены транзакции по заказам: '
                f'{', '.join(f'<code>{i.order_id}</code>' for i in done)}.'
            )
        if errored:
            notification_parts.append(
                f'❌ Не удалось подтвердить транзакции по заказам: '
                f'{', '.join(f'<code>{i.order_id}</code>' for i in errored)}.'
            )

        self.hub.telegram.send_notification(
            NotificationChannels.INFO,
            text='<b>' + '\n\n'.join(notification_parts) + '</b>',
        )

        await self.provider.storage.add_or_update_orders(*chain(done.keys(), errored))

    async def check_old_orders(self):
        o_dict = await self.provider.storage.get_orders(
            instance_id=self.hub.instance_id,
            same_instance=False,
            status=[SOS.WAITING_FOR_USERNAME, SOS.ERROR, SOS.UNPROCESSED, SOS.READY],
        )

        orders = {
            i for i in o_dict.values() if not (i.status is SOS.ERROR and not i.retries_left)
        }

        if not orders:
            return

        orders_dict = defaultdict(list)
        for i in orders:
            orders_dict[i.status].append(i)

        menu = await OldOrdersMenuContext(
            menu_id='autostars:old_orders_notification',
            chat_id=-1,
            errored_orders=len(orders_dict[SOS.ERROR]),
            waiting_username_orders=len(orders_dict[SOS.WAITING_FOR_USERNAME]),
            ready_orders=len(orders_dict[SOS.READY]),
            unprocessed_orders=len(orders_dict[SOS.UNPROCESSED]),
            callback_override=OpenMenu(
                menu_id='autostars:old_orders_notification',
                context_data={
                    'errored_orders': len(orders_dict[SOS.ERROR]),
                    'waiting_username_orders': len(orders_dict[SOS.WAITING_FOR_USERNAME]),
                    'ready_orders': len(orders_dict[SOS.READY]),
                    'unprocessed_orders': len(orders_dict[SOS.UNPROCESSED]),
                }
            )
        ).build_menu(self.hub.telegram.ui_registry)

        self.hub.telegram.send_notification(
            NotificationChannels.INFO,
            text=menu.total_text,
            reply_markup=menu.total_keyboard(convert=True),
        )
