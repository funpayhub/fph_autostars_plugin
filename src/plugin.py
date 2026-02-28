from __future__ import annotations

import asyncio
import logging
import traceback
from typing import TYPE_CHECKING

from aiogram.methods import SendDocument
from aiogram.types import BufferedInputFile
from pytoniq import LiteClient

from funpayhub.lib.telegram import Command
from funpayhub.lib.properties import ListParameter
from funpayhub.lib.translater import _ru
from funpayhub.lib.hub.text_formatters.category import InCategory

from funpayhub.app.plugin import Plugin
from funpayhub.app.formatters import GeneralFormattersCategory

from .fph import router as fph_router
from .other import NotificationChannels
from .funpay import funpay_router
from .storage import Sqlite3Storage
from .telegram import ROUTERS
from .formatters import StarsOrderCategory, StarsOrderFormatter, StarsOrderFormatterContext
from autostars.src.autostars_provider import AutostarsProvider
from .properties import AutostarsProperties
from .telegram.ui import BUILDERS
from .fragment_api import FragmentAPI
from .ton import Wallet
from .tonapi import TonAPI
from .transferer_service import TransferrerService
# from .telegram.middlewares import CryMiddleware


if TYPE_CHECKING:
    from aiogram import Router as TGRouter
    from funpaybotengine import Router as FPRouter

    from funpayhub.lib.properties import Properties
    from funpayhub.lib.telegram.ui import MenuBuilder
    from funpayhub.lib.hub.text_formatters import Formatter

    from funpayhub.app.dispatching import Router as HubRouter

    from .types import StarsOrder


AD_TEXT = (
    '✨ Звезды переведены автоматически плагином AutoStars для бесплатного бота FunPay Hub.  \n\n'
    '💻 GitHub: https://github.com/funpayhub/funpayhub \n'
    '💻 Plugin GitHub: https://github.com/funpayhub/fph_autostars_plugin \n'
    '✈️ Telegram: https://t.me/funpay_hub'
)


class AutostarsPlugin(Plugin):
    def __init__(self, *args):
        super().__init__(*args)

        self.api = TonAPI()
        self.provider = AutostarsProvider(self.api)
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

    async def telegram_routers(self) -> TGRouter | list[TGRouter]:
        return ROUTERS

    # async def setup_telegram_routers(self) -> None:
    #     mdlwr = CryMiddleware(self.props)
    #     self.hub.telegram.dispatcher.callback_query.outer_middleware(mdlwr)

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

        self.storage = await Sqlite3Storage.from_path('storage/autostars.sqlite3')
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
                        self.props.wallet.mnemonics.value, self.provider
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

        self.transfer_service = TransferrerService(
            self.hub,
            self.storage,
            self.logger,
        )

        self.transfer_service._on_success_callback = self.on_successful_transfer
        self.transfer_service._on_error_callback = self.on_transfer_error
        self.transfer_service._payload_gen = self.generate_payload_text

        self.hub.workflow_data.update(
            {
                'autostars_provider': self.provider,
                'autostars_storage': self.storage,
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
                    filename='autostars_service_crash_traceback.txt'
                )
            )
            self.hub.telegram.send_notification_from_obj(NotificationChannels.ERROR, call)

    async def generate_payload_text(self, order: StarsOrder, ref: str) -> str:
        text = self.props.messages.payload_message.value
        ad = self.props.messages.show_ad.value
        if not text:
            return ref if not ad else AD_TEXT + f'\n\n{ref}'

        ctx = StarsOrderFormatterContext(
            new_message_event=order.sale_event.related_new_message_event,
            order_event=order.sale_event,
            goods_to_deliver=[],
            stars_order=order,
        )

        try:
            pack = await self.hub.funpay.text_formatters.format_text(
                text=text,
                context=ctx,
                query=InCategory(StarsOrderCategory).or_(InCategory(GeneralFormattersCategory)),
            )
        except Exception:
            self.logger.error(
                _ru('Не удалось форматировать комментарий к транзакции.'),
                exc_info=True,
            )
            return ref if not ad else AD_TEXT + f'\n\n{ref}'

        total_text = ''.join(i for i in pack.entries if isinstance(i, str))
        if ad:
            total_text += f'\n\n{AD_TEXT}'

        if total_text:
            total_text += f'\n\n{ref}'
        else:
            total_text = ref
        return total_text

    async def on_transfer_error(self, *orders: StarsOrder) -> None:
        await asyncio.gather(*(self._on_transfer_error(i) for i in orders))
        message_text = self.hub.translater.translate(
            '<b>❌ Ошибка при трансфере TON для заказов {order_ids}.</b>',
        ).format(
            order_ids=', '.join(f'<code>{i.order_id}</code>' for i in orders),
        )
        self.hub.telegram.send_notification(
            NotificationChannels.ERROR,
            message_text,
        )

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
        message_text = self.hub.translater.translate(
            '<b>✅ Транзакции по заказам {order_ids} успешно выполнены.</b>',
        ).format(
            order_ids=', '.join(f'<code>{i.order_id}</code>' for i in orders),
        )
        self.hub.telegram.send_notification(
            NotificationChannels.INFO,
            message_text,
        )

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
