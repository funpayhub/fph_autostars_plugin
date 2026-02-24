from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from pytoniq import LiteClient


from funpayhub.lib.hub.text_formatters.category import InCategory
from funpayhub.lib.telegram import Command
from funpayhub.lib.translater import _ru

from funpayhub.app.plugin import Plugin

from .ton import Wallet, WalletProvider
from .funpay import funpay_router
from .storage import Sqlite3Storage
from .telegram import ROUTERS
from .properties import AutostarsProperties
from .fragment_api import FragmentAPI, FragmentAPIProvider
from .transferer_service import TransferrerService
from .formatters import StarsOrderFormatter, StarsOrderCategory, StarsOrderFormatterContext
from funpayhub.app.formatters import GeneralFormattersCategory
from .fph import router as fph_router


if TYPE_CHECKING:
    from aiogram import Router as TGRouter
    from funpaybotengine import Router as FPRouter
    from .types import StarsOrder
    from funpayhub.lib.properties import Properties
    from funpayhub.app.dispatching import Router as HubRouter
    from funpayhub.lib.hub.text_formatters import Formatter


class AutostarsPlugin(Plugin):
    def __init__(self, *args):
        super().__init__(*args)

        self.fragment_api_provider = FragmentAPIProvider()
        self.wallet_provider = WalletProvider()
        self.storage = None

        self.props: AutostarsProperties | None = None
        self.transferrer_service: TransferrerService | None = None

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
                command='transfer_stars',
                description='Потратить кровные звезды на какого-то.',
                setup=True,
            ),
        ]

    async def formatters(self) -> type[Formatter] | list[type[Formatter]] | None:
        return StarsOrderFormatter

    async def setup_formatters(self) -> None:
        self.hub.funpay.text_formatters.add_category(StarsOrderCategory)

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
            try:
                self.wallet_provider.wallet = await Wallet.from_mnemonics(
                    self.props.wallet.mnemonics.value,
                )
            except Exception:
                self.logger.error(
                    _ru('Произошла ошибка при подключении к кошельку.'), exc_info=True
                )

        self.transferrer_service = TransferrerService(
            self.hub,
            self.storage,
            self.fragment_api_provider,
            self.wallet_provider,
            self.logger,
        )

        self.transferrer_service._on_success_callback = self.on_successful_transfer

        self.hub.workflow_data.update(
            {
                'autostars_storage': self.storage,
                'autostars_wallet': self.wallet_provider,
                'autostars_fragment_api': self.fragment_api_provider,
                'autostars_service': self.transferrer_service,
            }
        )
        asyncio.create_task(self.transferrer_service.main_loop())

    async def on_successful_transfer(self, order: StarsOrder):
        message = self.props.messages.transaction_completed_message.value
        if not message:
            return

        ctx = StarsOrderFormatterContext(
            new_message_event=order.sale_event.related_new_message_event,
            order_event=order.sale_event,
            goods_to_deliver=[],
            stars_order=order
        )

        try:
            pack = await self.hub.funpay.text_formatters.format_text(
                text=message,
                context=ctx,
                query=InCategory(StarsOrderCategory).or_(InCategory(GeneralFormattersCategory))
            )
        except Exception:
            self.logger.error(
                _ru('Не удалось форматировать сообщение об успешном переводе звёзд.'),
                exc_info=True
            )
            # todo: err notification
            return

        try:
            await self.hub.funpay.send_messages_stack(pack, order.funpay_chat_id)
        except Exception:
            self.logger.error(
                _ru('Не удалось отправить сообщение об успешном переводе звёзд.'),
                exc_info=True
            )
            # todo: send notification

    @property
    def ready(self) -> bool:
        return self.fragment_api_provider.api is not None and self.wallet_provider.wallet is not None