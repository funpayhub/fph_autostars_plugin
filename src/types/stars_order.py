from __future__ import annotations


__all__ = ['StarsOrder']


import re

from pydantic import (
    BaseModel,
    PrivateAttr,
    ValidationError,
    computed_field,
    field_validator,
    field_serializer,
)
from funpaybotengine.types import Message, OrderPreview
from funpaybotengine.dispatching import NewSaleEvent, NewMessageEvent

from .enums import ErrorTypes, StarsOrderType, StarsOrderStatus


STARS_AMOUNT_RE = re.compile(r'^(\d+) (?:звёзд|Stars)(?:,|$)')
PCS_RE = re.compile(r'(?:^|, )(\d+) (?:шт|pcs)\.(?:,|$)')
USERNAME_RE = re.compile(r', @?([a-zA-Z0-9]+$)')


class StarsOrder(BaseModel):
    model_config = {'extra': 'allow'}

    message_obj: Message
    order_preview: OrderPreview
    telegram_username: str | None
    username_checked: bool = False
    recipient_id: str | None = None
    status: StarsOrderStatus = StarsOrderStatus.UNPROCESSED
    error: ErrorTypes | None = None
    fragment_request_id: str | None = None
    ton_transaction_id: str | None = None
    hub_instance: str
    retries_left: int = 3
    _sale_event: NewSaleEvent | None = PrivateAttr(default=None)

    @field_serializer('message_obj', mode='plain')
    def serialize_message(self, v: Message) -> str:
        return v.model_dump_json()

    @field_validator('message_obj', mode='before')
    def deserialize_message(cls, v: str | Message) -> Message:
        return Message.model_validate_json(v) if isinstance(v, str) else v

    @field_serializer('order_preview', mode='plain')
    def serialize_order_preview(self, v: OrderPreview) -> str | None:
        return v.model_dump_json()

    @field_validator('order_preview', mode='before')
    def deserialize_order_preview(cls, v: str | OrderPreview) -> OrderPreview:
        return OrderPreview.model_validate_json(v) if isinstance(v, str) else v

    @computed_field
    @property
    def order_stars_amount(self) -> int:
        try:
            match = STARS_AMOUNT_RE.match(self.order_preview.title)
            return int(match.group(1))
        except Exception as e:
            raise ValidationError(
                f'Unable to extract stars amount from {self.order_preview.title!r}.',
            ) from e

    @computed_field
    @property
    def order_amount(self) -> int:
        try:
            return int(PCS_RE.search(self.order_preview.title).group(1))
        except Exception:
            return 1

    @computed_field
    @property
    def stars_amount(self) -> int:
        return self.order_stars_amount * self.order_amount

    @computed_field
    @property
    def order_id(self) -> str:
        return self.order_preview.id

    @computed_field
    @property
    def funpay_username(self) -> str:
        return self.message_obj.meta.buyer_username

    @computed_field
    @property
    def funpay_chat_id(self) -> int:
        return self.message_obj.chat_id

    @property
    def type(self) -> StarsOrderType:
        return StarsOrderType.from_offer_title(self.order_preview.title)

    @staticmethod
    def get_telegram_username(order_title: str) -> str | None:
        match = USERNAME_RE.search(order_title)
        if not match:
            return None
        return match.group(1)

    @property
    def sale_event(self) -> NewSaleEvent:
        if self._sale_event is None:
            new_message_event = NewMessageEvent(object=self.message_obj, tag='autostar')
            self._sale_event = NewSaleEvent(
                object=self.message_obj,
                tag='autostar',
                related_new_message_event=new_message_event,
            )
            self._sale_event._order_preview = self.order_preview
        return self._sale_event

    def __hash__(self):
        return id(self)
