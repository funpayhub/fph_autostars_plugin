from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from logging import getLogger

from autostars.src.ton import Wallet
from autostars.src.storage import Storage
from autostars.src.ton.wallet import Transfer
from autostars.src.types.enums import ErrorTypes, StarsOrderStatus

from funpayhub.lib.translater import _ru

from .fragment_api.types import BuyStarsLink


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder
    from autostars.src.autostars_provider import AutostarsProvider

    from funpayhub.app.main import FunPayHub as FPH


logger = getLogger('funpayhub.com_github_qvvonk_funpayhub_autostars_plugin')


class TransferrerService:
    def __init__(self, hub: FPH, storage: Storage, provider: AutostarsProvider):
        self._storage = storage
        self._provider = provider
        self._hub = hub
        self._loop_stopped = False

        self._on_success_callback = None
        self._on_error_callback = None
        self._payload_gen = None

        self._stop = asyncio.Event()
        self._stopped = asyncio.Event()

    async def main_loop(self) -> None:
        try:
            await self._main_loop()
        except:
            self._stopped.set()
            raise

    async def _main_loop(self) -> None:
        logger.info(_ru('Autostars service запущен.'))
        self._stopped.clear()
        while True:
            if self._stop.is_set():
                self._stopped.set()
                logger.info(_ru('Autostars service остановлен.'))
                return

            await asyncio.sleep(2)

            fragment_api = self.provider.fragmentapi
            wallet = self.provider.wallet

            orders = await self.storage.get_ready_orders(instance_id=self.hub.instance_id)
            if not orders:
                logger.debug(_ru('Нет готовых для перевода заказов.'))
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
                if self._on_error_callback:
                    asyncio.create_task(self._on_error_callback(*orders.values()))
                continue

            for i in orders.values():
                i.status = StarsOrderStatus.TRANSFERRING
                i.retries_left -= 1
            await self.storage.add_or_update_orders(*orders.values())
            await self.transfer(wallet, *orders.values())

    async def transfer(self, wallet: Wallet, *orders: StarsOrder) -> None:
        orders_to_transfer: dict[StarsOrder, Transfer] = {}
        errored = []
        for i in orders:
            try:
                stars_link = await self.get_stars_link(i.recipient_id, i.stars_amount)
                payload = await self.generate_payload(
                    i,
                    stars_link.transaction.messages[0].clear_payload,
                )
                transfer = Transfer(
                    address=stars_link.transaction.messages[0].address,
                    amount=stars_link.transaction.messages[0].amount,
                    payload=payload,
                    valid_until=stars_link.transaction.valid_until,
                )
                orders_to_transfer[i] = transfer
            except Exception:
                logger.error(
                    _ru('Не удалось получить ссылку на оплату звезд по заказу %s (telegram: %s)'),
                    i.order_id,
                    i.telegram_username,
                    exc_info=True,
                )
                i.status = StarsOrderStatus.ERROR
                i.error = ErrorTypes.UNKNOWN
                errored.append(i)
                await self.storage.add_or_update_order(i)
                continue

        if errored:
            to_execute = [i for i in errored if i.retries_left <= 0]
            if to_execute:
                asyncio.create_task(self._on_error_callback(*to_execute))

        if not orders_to_transfer:
            return

        try:
            hash = await wallet.transfer(*orders_to_transfer.values())
        except Exception:  # todo: recreate wallet if timeout; check -13 code
            logger.error(
                'Не удалось выполнить перевод TON для заказов %s.',
                [i.order_id for i in orders_to_transfer],
                exc_info=True,
            )
            for i in orders_to_transfer:
                i.status = StarsOrderStatus.ERROR
                i.error = ErrorTypes.UNKNOWN
            await self.storage.add_or_update_orders(*orders_to_transfer)
            if self._on_error_callback:
                asyncio.create_task(self._on_error_callback(*orders_to_transfer))
            return

        logger.info(
            'Успешно перевел TON для заказов %s. Хэш транзакции: %s.',
            [i.order_id for i in orders_to_transfer],
            hash,
        )
        for i in orders_to_transfer:
            i.status = StarsOrderStatus.DONE
            i.transaction_hash = hash
        await self.storage.add_or_update_orders(*orders_to_transfer)
        if self._on_success_callback:
            asyncio.create_task(self._on_success_callback(*orders_to_transfer))

    async def generate_payload(self, order: StarsOrder, ref: str) -> str:
        if self._payload_gen is None:
            return ref

        try:
            r = await self._payload_gen(order, ref)
        except Exception:  # todo: log
            return ref
        return r or ref

    async def get_stars_link(self, recipient_id: str | None, amount: int) -> BuyStarsLink:
        init_link = await self.provider.fragmentapi.init_buy_stars_request(
            recipient=recipient_id,
            quantity=amount,
        )
        return await self.provider.fragmentapi.get_buy_stars_link(init_link.request_id)

    async def stop(self) -> None:
        if not self._stop.is_set():
            self._stop.set()
        await self._stopped.wait()

    @property
    def storage(self) -> Storage:
        return self._storage

    @property
    def provider(self) -> AutostarsProvider:
        return self._provider

    @property
    def hub(self) -> FPH:
        return self._hub
