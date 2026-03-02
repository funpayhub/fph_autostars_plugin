from __future__ import annotations

import time
import asyncio
from typing import TYPE_CHECKING

from autostars.src.ton import Wallet
from autostars.src.logger import logger
from autostars.src.ton.wallet import Transfer
from autostars.src.types.enums import ErrorTypes, StarsOrderStatus

from funpayhub.lib.translater import _ru


if TYPE_CHECKING:
    from autostars.src.types import StarsOrder
    from autostars.src.callbacks import Callbacks
    from autostars.src.autostars_provider import AutostarsProvider

    from funpayhub.app.main import FunPayHub as FPH


class TransferrerService:
    def __init__(self, provider: AutostarsProvider, callbacks: Callbacks):
        self._provider = provider
        self._hub = callbacks.hub
        self._loop_stopped = False
        self._callbacks = callbacks

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

            orders = await self.provider.storage.get_ready_orders(instance_id=self.hub.instance_id)
            orders = list(orders.values())
            if not orders:
                logger.debug(_ru('Нет готовых для перевода заказов.'))
                continue

            error = None
            if fragment_api is None:
                error = ErrorTypes.FRAGMENT_API_NOT_PROVIDED
            elif wallet is None:
                error = ErrorTypes.WALLET_NOT_PROVIDED

            if error is not None:  # todo: log
                for i in orders:
                    i.status = StarsOrderStatus.ERROR
                    i.error = error
                    i.retries_left = 0
                await self.provider.storage.add_or_update_orders(*orders)
                asyncio.create_task(self.callbacks.on_transactions_error(*orders))
                continue

            await self.provider.storage.add_or_update_orders(*orders)
            await self.transfer(wallet, *orders)
            errored, done = [], []
            for i in orders:
                if i.status is StarsOrderStatus.DONE:
                    done.append(i)
                elif i.status is StarsOrderStatus.ERROR and i.retries_left <= 0:
                    errored.append(i)

            if done:
                asyncio.create_task(self.callbacks.on_successful_transaction(*done))
            if errored:
                asyncio.create_task(self.callbacks.on_transactions_error(*errored))

    async def transfer(self, wallet: Wallet, *orders: StarsOrder) -> None:
        ready_orders: dict[StarsOrder, Transfer] = {}
        for i in orders:
            try:
                request = await self.provider.fragmentapi.init_buy_stars_request(
                    recipient=i.recipient_id,
                    quantity=i.stars_amount,
                )
                link = await self.provider.fragmentapi.get_buy_stars_link(request.request_id)
            except Exception:
                logger.error('Ошибка получения ссылки по заказу %s.', i.order_id, exc_info=True)
                i.status = StarsOrderStatus.ERROR
                i.error = ErrorTypes.UNABLE_TO_FETCH_STARS_LINK
                await self.provider.storage.add_or_update_order(i)
                continue

            payload = await self.callbacks.pyload_factory(
                i, link.transaction.messages[0].clear_payload
            )
            transfer = Transfer(
                address=link.transaction.messages[0].address,
                amount=link.transaction.messages[0].amount,
                payload=payload,
                valid_until=link.transaction.valid_until,
            )
            ready_orders[i] = transfer
            i.ref = link.transaction.messages[0].clear_payload
            i.fragment_request_id = request.request_id

        if not ready_orders:
            return

        ready_orders = await self.get_transferable_orders(ready_orders, wallet)
        not_enough_ton_orders = {k: v for k, v in ready_orders.items() if v not in ready_orders}

        if not_enough_ton_orders:
            for i in not_enough_ton_orders:
                i.status = StarsOrderStatus.ERROR
                i.error = ErrorTypes.NOT_ENOUGH_TON
                i.retries_left = 0
            await self.provider.storage.add_or_update_orders(*not_enough_ton_orders)

        if not ready_orders:
            return

        boc, in_hash = await wallet.create_external_transfer_message(*ready_orders.values())
        for i in ready_orders:
            i.in_msg_hash, i.status = in_hash, StarsOrderStatus.TRANSFERRING
        await self.provider.storage.add_or_update_orders(*ready_orders)

        try:
            await self.provider.tonapi.send_message(boc)
        except Exception:
            logger.error('Ошибка перевода %s.', [i.order_id for i in ready_orders], exc_info=True)
            for i in ready_orders:
                i.status, i.error = StarsOrderStatus.ERROR, ErrorTypes.UNKNOWN
            await self.provider.storage.add_or_update_orders(*ready_orders)
            return

        try:
            tr = await self.provider.wallet.wait_for_transfer(in_hash, int(time.time() + 60))
        except TimeoutError:
            logger.error('Таймаут ожидания транзакции с in_msg_hash=%s.', in_hash)
            for i in ready_orders:
                i.status, i.error = StarsOrderStatus.ERROR, ErrorTypes.UNKNOWN
            await self.provider.storage.add_or_update_orders(*ready_orders)
            return

        logger.info('Перевел по заказам %s. Хэш: %s.', [i.order_id for i in ready_orders], tr.hash)
        for i in ready_orders:
            i.status, i.transaction_hash = StarsOrderStatus.DONE, tr.hash
        await self.provider.storage.add_or_update_orders(*ready_orders)

    async def get_transferable_orders(
        self,
        orders_dict: dict[StarsOrder, Transfer],
        wallet: Wallet
    ) -> dict[StarsOrder, Transfer]:
        orders = sorted(orders_dict.items(), key=lambda x: x[1].amount)
        balance = await wallet.get_balance() - int(0.1) * 1_000_000_000
        transferable_orders: dict[StarsOrder, Transfer] = {}
        total = 0
        for order, transfer in orders:
            if total + transfer.amount > balance:
                break
            total += transfer.amount
            transferable_orders[order] = transfer

        return transferable_orders

    async def stop(self) -> None:
        if not self._stop.is_set():
            self._stop.set()
        await self._stopped.wait()

    @property
    def provider(self) -> AutostarsProvider:
        return self._provider

    @property
    def hub(self) -> FPH:
        return self._hub

    @property
    def callbacks(self) -> Callbacks:
        return self._callbacks
