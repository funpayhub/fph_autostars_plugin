from __future__ import annotations

import time
import asyncio
from typing import TYPE_CHECKING

from autostars.src.fragment_api import FragmentAPI
from autostars.src.ton import Wallet
from autostars.src.logger import logger
from autostars.src.ton.wallet import Transfer
from autostars.src.types.enums import ErrorTypes, StarsOrderStatus as SOS
from typing import Any
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

            fragment_api = self.provider.fragment
            wallet = self.provider.wallet

            if fragment_api is None or wallet is None:
                logger.warning(f'Fragment API или кошелек не указан.')
                continue

            orders = (await self.provider.storage.get_ready_orders(self.hub.instance_id)).values()
            if not orders:
                logger.debug(_ru('Нет готовых для перевода заказов.'))
                continue

            for i in orders:
                i.retries_left -= 1
            await self.provider.storage.add_or_update_orders(*orders)

            await self.transfer(fragment_api, wallet, *orders)

            errored, done = [], []
            for i in orders:
                if i.status is SOS.DONE:
                    done.append(i)
                elif i.status is SOS.ERROR and i.retries_left <= 0:
                    errored.append(i)

            if done:
                asyncio.create_task(self.callbacks.on_successful_transaction(*done))
            if errored:
                asyncio.create_task(self.callbacks.on_transactions_error(*errored))

    async def transfer(self, fragment: FragmentAPI, wallet: Wallet, *orders: StarsOrder) -> None:
        tasks = await asyncio.gather(*(self.stars_link(fragment, i) for i in orders))
        await self.provider.storage.add_or_update_orders(*orders)

        ready_orders = {i[0]: i[1] for i in tasks if i[1] is not None}
        if not ready_orders:
            return

        try:
            approved_orders = await self.get_transferable_orders(ready_orders, wallet)
            not_enough_ton_orders = {k for k in ready_orders if k not in approved_orders}
        except Exception:
            logger.error(f'Ошибка получения баланса TON.', exc_info=True)
            await self.update_orders(*ready_orders.values(),  status=SOS.ERROR, error=ErrorTypes.UNKNOWN)
            return

        if not_enough_ton_orders:
            await self.update_orders(
                *not_enough_ton_orders,
                status=SOS.ERROR,
                error=ErrorTypes.NOT_ENOUGH_TON,
                retries_left=0
            )

        if not ready_orders:
            return

        await self.transfer_orders(wallet, approved_orders)

    async def stars_link(self, api: FragmentAPI, o: StarsOrder) -> tuple[StarsOrder, Transfer | None]:
        try:
            req = await api.init_buy_stars_request(o.recipient_id, o.stars_amount)
            link = await api.get_buy_stars_link(req.request_id)
        except Exception:
            logger.error('Ошибка получения ссылки по заказу %s.', o.order_id, exc_info=True)
            o.status, o.error = SOS.ERROR, ErrorTypes.UNKNOWN
            return o, None

        o.ref, o.fragment_request_id = link.transaction.messages[0].clear_payload, req.request_id

        return o, Transfer(
            address=link.transaction.messages[0].address,
            amount=link.transaction.messages[0].amount,
            body=await self.callbacks.gen_payload(o, link.transaction.messages[0].clear_payload),
            valid_until=link.transaction.valid_until,
        )

    async def transfer_orders(self, wallet: Wallet, orders: dict[StarsOrder, Transfer]) -> None:
        boc, in_hash = await wallet.create_external_transfer_message(*orders.values())
        await self.update_orders(*orders.values(), in_msg_hash=in_hash,  status=SOS.TRANSFERRING)

        try:
            await self.provider.tonapi.send_message(boc)
        except Exception:
            logger.error('Ошибка перевода %s.', [i.order_id for i in orders], exc_info=True)
            await self.update_orders(*orders.values(), status=SOS.ERROR, error=ErrorTypes.UNKNOWN)
            return

        try:
            tr = await self.provider.wallet.wait_for_transfer(in_hash, int(time.time() + 60))
        except TimeoutError:
            logger.error('Таймаут ожидания транзакции с in_msg_hash=%s.', in_hash)
            await self.update_orders(*orders.values(), status=SOS.ERROR, error=ErrorTypes.UNKNOWN)
            return

        logger.info('Перевел по заказам %s. Хэш: %s.', [i.order_id for i in orders], tr.hash)
        await self.update_orders(*orders.values(), status=SOS.DONE, transaction_hash=tr.hash)

    async def get_transferable_orders(
        self, orders_dict: dict[StarsOrder, Transfer], wallet: Wallet
    ) -> dict[StarsOrder, Transfer]:
        balance = await wallet.get_balance() - int(0.1) * 1_000_000_000
        transferable_orders: dict[StarsOrder, Transfer] = {}
        total = 0
        for order, transfer in sorted(orders_dict.items(), key=lambda x: x[1].amount):
            if total + transfer.amount > balance:
                break
            total += transfer.amount
            transferable_orders[order] = transfer

        return transferable_orders

    async def update_orders(self, *orders: StarsOrder, save: bool = True, **kwargs: Any) -> None:
        for i in orders:
            for k, v in kwargs.items():
                setattr(i, k, v)

        if save:
            await self.provider.storage.add_or_update_orders(*orders)

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
