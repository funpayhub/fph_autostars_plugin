from __future__ import annotations

import asyncio
import logging
import traceback
from typing import TYPE_CHECKING

from pytoniq import LiteClient
from aiogram.types import BufferedInputFile
from aiogram.methods import SendDocument

from funpayhub.lib.telegram import Command
from funpayhub.lib.properties import ListParameter
from funpayhub.lib.translater import _ru

from funpayhub.app.plugin import Plugin

from .fph import router as fph_router
from .ton import Wallet
from .other import NotificationChannels
from .funpay import funpay_router
from .tonapi import TonAPI
from .storage import Sqlite3Storage
from .telegram import ROUTERS
from .formatters import StarsOrderCategory, StarsOrderFormatter
from .properties import AutostarsProperties
from .telegram.ui import BUILDERS
from .fragment_api import FragmentAPI
from .transferer_service import TransferrerService
from .autostars_provider import AutostarsProvider
from .callbacks import Callbacks


if TYPE_CHECKING:
    from aiogram import Router as TGRouter
    from funpaybotengine import Router as FPRouter

    from funpayhub.lib.properties import Properties
    from funpayhub.lib.telegram.ui import MenuBuilder
    from funpayhub.lib.hub.text_formatters import Formatter

    from funpayhub.app.dispatching import Router as HubRouter


class AutostarsPlugin(Plugin):
    def __init__(self, *args):
        super().__init__(*args)

        self.api = TonAPI()
        self.provider = None
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
        return StarsOrderFormatter

    async def setup_formatters(self) -> None:
        self.hub.funpay.text_formatters.add_category(StarsOrderCategory)

    async def menus(self) -> type[MenuBuilder] | list[type[MenuBuilder]]:
        return BUILDERS

    async def post_setup(self) -> None:
        logger = logging.getLogger(LiteClient.__name__)
        logger.setLevel(logging.WARNING)

        storage = await Sqlite3Storage.from_path('storage/autostars.sqlite3')
        self.provider = AutostarsProvider(TonAPI(), storage)

        if self.props.wallet.cookies.value and self.props.wallet.fragment_hash.value:
            self.logger.info(_ru('Cookie и Hash найдены в настройках. Создаю FragmentAPI.'))
            self.provider._fragmentapi = FragmentAPI(
                self.props.wallet.cookies.value,
                self.props.wallet.fragment_hash.value,
            )

        if self.props.wallet.mnemonics.value:
            self.logger.info(_ru('Мнемоники найдены в настройках. Создаю кошелек.'))
            for i in range(3):
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
                    break
                except Exception:
                    self.logger.error(
                        _ru('Произошла ошибка при подключении к кошельку. Попытка: %d/3.'),
                        i + 1,
                        exc_info=True,
                    )
                    await asyncio.sleep(2)
            else:
                self.hub.telegram.send_notification(
                    NotificationChannels.ERROR,
                    self.hub.translater.translate(
                        '<b>[❌ CRITICAL ❌]\n'
                        'Не удалось подключиться к TON кошельку.\n\n'
                        'Подробности в логах.</b>',
                    ),
                )

        self.transfer_service = TransferrerService(self.hub, self.provider, self.callbacks)

        self.hub.workflow_data.update(
            {
                'autostars_provider': self.provider,
                'autostars_storage': self.provider.storage,
                'autostars_service': self.transfer_service,
            },
        )
        task = asyncio.create_task(self.transfer_service.main_loop())
        task.add_done_callback(self.service_done_callback)

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
