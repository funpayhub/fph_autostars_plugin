from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from funpayhub.lib.translater import _ru

from .ton import WalletProvider
from .storage import Storage
from .ton.wallet import Transfer
from .types.enums import ErrorTypes, StarsOrderStatus
from .fragment_api import FragmentAPIProvider
from .fragment_api.types import BuyStarsLink


if TYPE_CHECKING:
    from funpayhub.app.main import FunPayHub as FPH

    from .types import StarsOrder


class TransferrerService:
    def __init__(
        self,
        hub: FPH,
        storage: Storage,
        api_provider: FragmentAPIProvider,
        wallet_provider: WalletProvider,
        logger: logging.Logger,
    ):
        self._storage = storage
        self._api_provider = api_provider
        self._wallet_provider = wallet_provider
        self._hub = hub
        self._loop_stopped = False
        self.logger = logger

        self._on_success_callback = None
        self._on_error_callback = None

    async def main_loop(self) -> None:
        self.logger.info(_ru('Autostars service запущен.'))
        while True:
            await asyncio.sleep(2)

            fragment_api = self.api_provider.api
            wallet = self.wallet_provider.wallet

            orders = await self.storage.get_ready_orders(instance_id=self.hub.instance_id)
            if not orders:
                self.logger.debug(_ru('Нет готовых для перевода заказов.'))
                continue

            error = None
            if fragment_api is None:
                error = ErrorTypes.FRAGMENT_API_NOT_PROVIDED
            elif wallet is None:
                error = ErrorTypes.WALLET_NOT_PROVIDED

            if error is not None:  # todo: log
                for i in orders.values():
                    i.status = StarsOrderStatus.ERROR
                    i.error = error
                    i.retries_left = 0
                await self.storage.add_or_update_orders(*orders.values())
                continue

            for i in orders.values():
                i.status = StarsOrderStatus.TRANSFERRING
                i.retries_left -= 1
                await self.storage.add_or_update_order(i)

            orders_to_transfer: list[StarsOrder] = []
            transfers = []
            for i in orders.values():
                try:
                    stars_link = await self.get_stars_link(i.recipient_id, i.stars_amount)
                    orders_to_transfer.append(i)
                except Exception:
                    self.logger.error(
                        _ru(
                            'Не удалось получить ссылку на оплату звезд для заказа %s '
                            '(telegram: %s | recipient id: %s).',
                        ),
                        i.order_id,
                        i.telegram_username,
                        i.recipient_id,
                        exc_info=True,
                    )
                    i.status = StarsOrderStatus.ERROR
                    i.error = ErrorTypes.UNKNOWN
                    await self.storage.add_or_update_order(i)
                    continue

                transfer = Transfer(
                    address=stars_link.transaction.messages[0].address,
                    amount=stars_link.transaction.messages[0].amount,
                    payload=stars_link.transaction.messages[0].clear_payload,
                    valid_until=stars_link.transaction.valid_until,
                )
                transfers.append(transfer)

            if transfers:
                try:
                    hash = await wallet.transfer(*transfers)
                except Exception:
                    self.logger.error(
                        'Не удалось выполнить перевод TON для заказов %s.',
                        [i.order_id for i in orders_to_transfer],
                        exc_info=True,
                    )
                    for i in orders_to_transfer:
                        i.status = StarsOrderStatus.ERROR
                        i.error = ErrorTypes.UNKNOWN
                    await self.storage.add_or_update_orders(*orders_to_transfer)
                else:
                    self.logger.info(
                        'Успешно перевел TON для заказов %s. Хэш транзакции: %s.',
                        [i.order_id for i in orders_to_transfer],
                        hash,
                    )
                    for i in orders_to_transfer:
                        i.status = StarsOrderStatus.DONE
                        i.ton_transaction_id = hash
                        if self._on_success_callback:
                            asyncio.create_task(self._on_success_callback(i))
                    await self.storage.add_or_update_order(*orders_to_transfer)

    async def get_stars_link(self, recipient_id: str, amount: int) -> BuyStarsLink:
        init_link = await self.api_provider.api.init_buy_stars_request(
            recipient=recipient_id,
            quantity=amount,
        )
        return await self.api_provider.api.get_buy_stars_link(init_link.request_id)

    @property
    def storage(self) -> Storage:
        return self._storage

    @property
    def api_provider(self) -> FragmentAPIProvider:
        return self._api_provider

    @property
    def wallet_provider(self) -> WalletProvider:
        return self._wallet_provider

    @property
    def hub(self) -> FPH:
        return self._hub
