from uuid import UUID

from .exceptions import StorageFullError
from .items import Item
from .validation import require_text


# Warren's contribution: the physical shelf/closet has capacity and placement rules.
class StorageSpace:
    def __init__(self, location: str, capacity: int) -> None:
        self._location = require_text(location, "location")
        if capacity < 1:
            raise ValueError("capacity must be at least one.")
        self._capacity = capacity
        self._stored_ids: set[UUID] = set()

    @property
    def location(self) -> str:
        return self._location

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def item_count(self) -> int:
        return len(self._stored_ids)

    def has_room(self) -> bool:
        return self.item_count < self._capacity

    def _store(self, item: Item) -> None:
        if item.id in self._stored_ids:
            return
        if not self.has_room():
            raise StorageFullError("The campus storage space is full.")
        self._stored_ids.add(item.id)

    def _remove(self, item: Item) -> None:
        self._stored_ids.discard(item.id)

    def contains(self, item: Item) -> bool:
        return item.id in self._stored_ids
