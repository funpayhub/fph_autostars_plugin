from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import dataclass

from funpayhub.lib.telegram.fsm import State


if TYPE_CHECKING:
    from aiogram.types import Message


@dataclass
class ViewingOrderInfo(State, identifier='autostars:viewing-order-info'):
    state_message: Message


@dataclass
class MarkingAsDoneState(State, identifier='autostars:marking-as-done'):
    state_message: Message
