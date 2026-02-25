from __future__ import annotations


__all__ = ['Storage', 'Sqlite3Storage']


from typing import Any, Self
from abc import ABC, abstractmethod
from pathlib import Path

import aiosqlite
from aiosqlite import Cursor, Connection

from ..types import StarsOrder
from ..types.enums import StarsOrderStatus


class Storage(ABC):
    @abstractmethod
    async def add_or_update_order(self, order: StarsOrder) -> None: ...

    @abstractmethod
    async def add_or_update_orders(self, *orders: StarsOrder) -> None: ...

    @abstractmethod
    async def get_order(self, order_id: str) -> StarsOrder | None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def get_orders(
        self,
        *order_ids: str,
        status: StarsOrderStatus | list[StarsOrderStatus] | None = None,
    ) -> dict[str, StarsOrder]: ...

    @abstractmethod
    async def get_ready_orders(
        self,
        instance_id: str,
        amount: int = 25,
    ) -> dict[str, StarsOrder]: ...


class Sqlite3Storage(Storage):
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._conn: Connection | None = None

        self._expected_schema = {
            'id': 'TEXT',
            'telegram_username': 'TEXT',
            'funpay_chat_id': 'INTEGER',
            'status': 'TEXT',
            'error': 'TEXT',
            'fragment_request_id': 'TEXT',
            'ton_transaction_id': 'TEXT',
            'event_obj': 'TEXT',
            'order_preview': 'TEXT',
            'created_at': 'INTEGER',
        }

    async def setup(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row

        await self._conn.execute("""CREATE TABLE IF NOT EXISTS "orders" (
	            "order_id"	          TEXT    NOT NULL UNIQUE,
                "order_stars_amount"  INTEGER NOT NULL,
                "order_amount"        INTEGER NOT NULL,
	            "stars_amount"        INTEGER NOT NULL,
	            "funpay_username"     TEXT    NOT NULL,
                "username_checked"    BOOLEAN NOT NULL DEFAULT 0,
                "funpay_chat_id"      INTEGER NOT NULL,
                "telegram_username"	  TEXT,
                "recipient_id"        TEXT,
                "status"	          TEXT    NOT NULL
                CHECK( status IN (
                    'UNPROCESSED', 
                    'WAITING_FOR_USERNAME', 
                    'READY', 
                    'TRANSFERRING', 
                    'DONE', 
                    'ERROR'
                )),
            
                "error"	              TEXT
                CHECK(error IS NULL OR error IN ('NOT_ENOUGH_TON', 'TRANSFER_ERROR', 'UNKNOWN')),
                "fragment_request_id" TEXT,
                "ton_transaction_id"  TEXT,
                "message_obj"	      TEXT    NOT NULL,
                "order_preview"	      TEXT    NOT NULL,
                "hub_instance"        TEXT    NOT NULL,
                "retries_left"        INTEGER NOT NULL,
                PRIMARY KEY("order_id")
);""")

        # todo: add table structure check

    async def stop(self):
        await self._conn.close()

    async def add_or_update_order(self, order: StarsOrder, commit: bool = True) -> None:
        data = order.model_dump(mode='json')
        keys = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        values = tuple(data.values())

        await self.raw_query(
            f'INSERT OR REPLACE INTO orders ({keys}) VALUES ({placeholders})',
            *values,
            commit=False,
        )

        if commit:
            await self._conn.commit()

    async def add_or_update_orders(self, *orders: StarsOrder) -> None:
        for order in orders:
            await self.add_or_update_order(order, commit=False)
        await self._conn.commit()

    async def get_order(self, order_id: str) -> StarsOrder | None:
        cursor = await self.raw_query('SELECT * FROM orders WHERE order_id = ?', order_id)
        data = await cursor.fetchone()
        if not data:
            return None

        return StarsOrder.model_validate(dict(data))

    async def get_orders(
        self,
        *order_ids: str,
        status: StarsOrderStatus | list[StarsOrderStatus] | None = None,
    ) -> dict[str, StarsOrder]:
        sql = 'SELECT * FROM orders'
        conditions = []
        params = []

        # фильтр по order_id
        if order_ids:
            placeholders = ', '.join(['?'] * len(order_ids))
            conditions.append(f'order_id IN ({placeholders})')
            params.extend(order_ids)

        # фильтр по статусу
        if status is not None:
            if isinstance(status, list):
                placeholders = ', '.join(['?'] * len(status))
                conditions.append(f'status IN ({placeholders})')
                params.extend([s.value for s in status])
            else:
                conditions.append('status = ?')
                params.append(status.value)

        if conditions:
            sql += ' WHERE ' + ' AND '.join(conditions)

        cursor = await self.raw_query(sql, *params, commit=False)
        return {
            row['order_id']: StarsOrder.model_validate(dict(row))
            for row in await cursor.fetchall()
        }

    async def get_ready_orders(self, instance_id: str, amount=25) -> dict[str, StarsOrder]:
        sql = (
            'SELECT * FROM orders '
            "WHERE (status = 'READY' OR (status = 'ERROR' AND retries_left > 0)) AND hub_instance = ? "
            'LIMIT ?'
        )

        cursor = await self.raw_query(sql, instance_id, amount, commit=False)
        return {
            row['order_id']: StarsOrder.model_validate(dict(row))
            for row in await cursor.fetchall()
        }

    async def raw_query(
        self,
        query: str,
        *args: Any,
        cursor: Cursor | None = None,
        commit: bool = True,
    ) -> Cursor:
        cursor = cursor if cursor is not None else self._conn
        cursor = await cursor.execute(query, args)
        if commit:
            await self._conn.commit()
        return cursor

    @property
    def path(self) -> Path:
        return self._path

    @classmethod
    async def from_path(cls, path: str | Path) -> Self:
        storage = Sqlite3Storage(path)
        await storage.setup()
        return storage
