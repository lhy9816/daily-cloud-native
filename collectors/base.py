from __future__ import annotations
from abc import ABC, abstractmethod
from models import RawItem


class BaseCollector(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def collect(self) -> list[RawItem]:
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...
