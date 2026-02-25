from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from pytoniq import LiteClient

from funpayhub.lib.telegram import Command
from funpayhub.lib.properties import ListParameter
from funpayhub.lib.translater import _ru
from funpayhub.lib.hub.text_formatters.category import InCategory

from funpayhub.app.plugin import Plugin
from funpayhub.app.formatters import GeneralFormattersCategory
from .exceptions import TonWalletError
import traceback

from .fph import router as fph_router
from .ton import WalletProvider
from .other import NotificationChannels
from .funpay import funpay_router
from .storage import Sqlite3Storage
# from .telegram import ROUTERS
from .formatters import StarsOrderCategory, StarsOrderFormatter, StarsOrderFormatterContext
from .properties import AutostarsProperties
from .telegram.ui import BUILDERS
from .fragment_api import FragmentAPI, FragmentAPIProvider
from .transferer_service import TransferrerService


if TYPE_CHECKING:
    from aiogram import Router as TGRouter
    from funpaybotengine import Router as FPRouter

    from funpayhub.lib.properties import Properties
    from funpayhub.lib.telegram.ui import MenuBuilder
    from funpayhub.lib.hub.text_formatters import Formatter

    from funpayhub.app.dispatching import Router as HubRouter

    from .types import StarsOrder


class AutostarsPlugin(Plugin):
    def __init__(self, *args):
        super().__init__(*args)

        self.fragment_api_provider = FragmentAPIProvider()
        self.wallet_provider = WalletProvider()
        self.storage = None

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

    # async def telegram_routers(self) -> TGRouter | list[TGRouter]:
    #     return ROUTERS

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
                setup=True
            )
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

        self.storage = await Sqlite3Storage.from_path('storage/autostars.sqlite3')
        if self.props.wallet.cookies.value and self.props.wallet.fragment_hash.value:
            self.logger.info(_ru('Cookie и Hash найдены в настройках. Создаю FragmentAPI.'))
            self.fragment_api_provider.api = FragmentAPI(
                self.props.wallet.cookies.value,
                self.props.wallet.fragment_hash.value,
            )

        if self.props.wallet.mnemonics.value:
            self.logger.info(_ru('Мнемоники найдены в настройках. Создаю кошелек.'))
            for i in range(3):
                try:
                    await self.wallet_provider.remake_wallet(self.props.wallet.mnemonics.value)
                    break
                except TonWalletError:
                    self.logger.error(
                        _ru('Произошла ошибка при подключении к кошельку. Попытка: %d/3.'),
                        i+1,
                        exc_info=True,
                    )
            else:
                self.hub.telegram.send_notification(
                    NotificationChannels.ERROR,
                    self.hub.translater.translate(
                        '<b>[❌ CRITICAL ❌]\n'
                        'Не удалось подключиться к TON кошельку.\n\n'
                        'Подробности в логах.</b>'
                    )
                )


        self.transfer_service = TransferrerService(
            self.hub,
            self.storage,
            self.fragment_api_provider,
            self.wallet_provider,
            self.logger,
        )

        self.transfer_service._on_success_callback = self.on_successful_transfer
        self.transfer_service._on_error_callback = self.on_transfer_error

        self.hub.workflow_data.update(
            {
                'autostars_storage': self.storage,
                'autostars_wallet': self.wallet_provider,
                'autostars_fragment_api': self.fragment_api_provider,
                'autostars_service': self.transfer_service,
            },
        )
        task = asyncio.create_task(self.transfer_service.main_loop())
        task.add_done_callback(self.service_done_callback)

    # ------------------------------------------
    # ---------------- Callbacks ---------------
    # ------------------------------------------
    def service_done_callback(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.critical('Autostars service is dead.', exc_info=True)
            error_file = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            self.hub.telegram.send_notification(
                NotificationChannels.ERROR,
                self.hub.translater.translate(
                    '<b>[❌ CRITICAL ❌]\n\n'
                    '☠️ Autostars сервис умер.\n'
                    '☠️ Переводы не будут совершаться.\n'
                    '☠️ Обязательно передайте это сообщение разработчику.\n'
                    '☠️ В данной ситуации поможет только перезапуск FunPay Hub.\n\n'
                    '☠️ Подробности в логах.</b>'
                ),
                document=error_file
            )

    async def on_transfer_error(self, *orders: StarsOrder) -> None:
        await asyncio.gather(*(self._on_successful_transfer(i) for i in orders))
        # todo: telegram notification

    async def _on_transfer_error(self, order: StarsOrder) -> None:
        message = self.props.messages.transaction_failed_message.value
        if not message:
            return

        ctx = StarsOrderFormatterContext(
            new_message_event=order.sale_event.related_new_message_event,
            order_event=order.sale_event,
            goods_to_deliver=[],
            stars_order=order,
        )

        try:
            pack = await self.hub.funpay.text_formatters.format_text(
                text=message,
                context=ctx,
                query=InCategory(StarsOrderCategory).or_(InCategory(GeneralFormattersCategory)),
            )
        except Exception:
            self.logger.error(
                _ru('Не удалось форматировать сообщение об ошибка перевода звёзд.'),
                exc_info=True,
            )
            return

        try:
            await self.hub.funpay.send_messages_stack(pack, order.funpay_chat_id)
        except Exception:
            self.logger.error(
                _ru('Не удалось отправить сообщение об ошибке перевода звёзд.'),
                exc_info=True,
            )

    async def on_successful_transfer(self, *orders: StarsOrder) -> None:
        await asyncio.gather(*(self._on_successful_transfer(i) for i in orders))
        # todo: send telegram notification

    async def _on_successful_transfer(self, order: StarsOrder) -> None:
        message = self.props.messages.transaction_completed_message.value
        if not message:
            return

        ctx = StarsOrderFormatterContext(
            new_message_event=order.sale_event.related_new_message_event,
            order_event=order.sale_event,
            goods_to_deliver=[],
            stars_order=order,
        )

        try:
            pack = await self.hub.funpay.text_formatters.format_text(
                text=message,
                context=ctx,
                query=InCategory(StarsOrderCategory).or_(InCategory(GeneralFormattersCategory)),
            )
        except Exception:
            self.logger.error(
                _ru('Не удалось форматировать сообщение об успешном переводе звёзд.'),
                exc_info=True,
            )
            return

        try:
            await self.hub.funpay.send_messages_stack(pack, order.funpay_chat_id)
        except Exception:
            self.logger.error(
                _ru('Не удалось отправить сообщение об успешном переводе звёзд.'),
                exc_info=True,
            )

    @property
    def ready(self) -> bool:
        return (
            self.fragment_api_provider.api is not None and self.wallet_provider.wallet is not None
        )
