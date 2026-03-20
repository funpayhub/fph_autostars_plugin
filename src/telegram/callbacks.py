from __future__ import annotations

from typing import Literal, Annotated

from pydantic import BeforeValidator, PlainSerializer
from autostars.src.types.enums import StarsOrderStatus

from funpayhub.lib.telegram.callback_data import CallbackData


def status_field_validator(v: str) -> StarsOrderStatus:
    return StarsOrderStatus(v)


def status_field_serializer(v: StarsOrderStatus) -> str:
    return v.value


StatusField = Annotated[
    StarsOrderStatus,
    BeforeValidator(status_field_validator),
    PlainSerializer(status_field_serializer),
]


class ListOldOrders(CallbackData, identifier='autostars-list_old_orders'):
    status: StatusField


class OldOrdersAction(CallbackData, identifier='autostars-old_orders_action'):
    status: StatusField
    action: Literal['dont_ignore', 'mark_done', 'mark_done', 'mark_refunded', 'delete']
