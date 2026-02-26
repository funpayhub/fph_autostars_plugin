from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from abc import ABC, abstractmethod

from pydantic import BaseModel, computed_field

from temp.autostars.src.fragment_api.types import FragmentResponse


class FragmentMethod[ReturnT](BaseModel, ABC):
    model_config = {'extra': 'allow'}

    if TYPE_CHECKING:
        __model_to_build__: ClassVar[type[FragmentResponse]]
    else:

        @property
        @abstractmethod
        def __model_to_build__(self) -> type[FragmentResponse]:
            pass

    @computed_field
    @property
    @abstractmethod
    def method(self) -> str:
        pass
