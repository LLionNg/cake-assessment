from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLM(ABC):
    @abstractmethod
    def parse(self, system: str, payload: dict, schema: type[T]) -> T:
        """Send instructions plus a JSON payload and return a validated `schema` instance."""
