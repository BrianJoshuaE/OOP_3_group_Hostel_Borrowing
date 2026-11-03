from typing import Iterable, Protocol

from .enums import ItemCategory, ItemStatus
from .items import Item


# Warren's contribution: search, filtering, sorting, and structural duck typing.
class CareInstructionProvider(Protocol):
    def get_care_instructions(self) -> str: ...


class CatalogService:
    def __init__(self, inventory: list[Item]) -> None:
        self._inventory = inventory

    def find_available(self, category: ItemCategory | None = None) -> tuple[Item, ...]:
        return tuple(sorted(
            (item for item in self._inventory
             if item.status is ItemStatus.AVAILABLE
             and (category is None or item.get_category() is category)),
            key=lambda item: item.name.casefold(),
        ))

    def search(self, query: str) -> tuple[Item, ...]:
        normalized = query.strip().casefold()
        if not normalized:
            return ()
        matches = (item for item in self._inventory
                   if normalized in item.name.casefold()
                   or normalized in item.description.casefold())
        return tuple(sorted(matches, key=lambda item: item.name.casefold()))

    def sort_by_added_date(self, items: Iterable[Item]) -> tuple[Item, ...]:
        return tuple(sorted(items, key=lambda item: item.added_on))


def care_instructions_for(item: CareInstructionProvider) -> str:
    """Use any object with the expected method; no inheritance is required."""
    return item.get_care_instructions()
