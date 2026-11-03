from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID, uuid4

from .enums import ItemCategory, ItemCondition, ItemStatus
from .exceptions import InvalidStateError, ItemUnavailableError
from .validation import require_text


# Kevin's contribution: an abstract item and concrete inventory types demonstrate inheritance and overriding.
class Item(ABC):
    def __init__(
        self,
        name: str,
        description: str,
        condition: ItemCondition = ItemCondition.GOOD,
        item_id: UUID | None = None,
        added_on: date | None = None,
    ) -> None:
        if not isinstance(condition, ItemCondition):
            raise TypeError("condition must be an ItemCondition.")
        self._id = item_id or uuid4()
        self._name = require_text(name, "name")
        self._description = require_text(description, "description")
        self._condition = condition
        self._status = ItemStatus.AVAILABLE
        self._added_on = added_on or date.today()

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = require_text(value, "name")

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = require_text(value, "description")

    @property
    def condition(self) -> ItemCondition:
        return self._condition

    @property
    def status(self) -> ItemStatus:
        return self._status

    @property
    def added_on(self) -> date:
        return self._added_on

    @abstractmethod
    def get_category(self) -> ItemCategory:
        raise NotImplementedError

    @abstractmethod
    def get_care_instructions(self) -> str:
        raise NotImplementedError

    def _set_condition(self, condition: ItemCondition) -> None:
        if not isinstance(condition, ItemCondition):
            raise TypeError("condition must be an ItemCondition.")
        self._condition = condition

    def _reserve(self) -> None:
        if self._status is not ItemStatus.AVAILABLE:
            raise ItemUnavailableError("Only available items can be reserved.")
        self._status = ItemStatus.RESERVED

    def _check_out(self) -> None:
        if self._status not in (ItemStatus.AVAILABLE, ItemStatus.RESERVED):
            raise ItemUnavailableError("Item is not available for checkout.")
        self._status = ItemStatus.ON_LOAN

    def _mark_available(self) -> None:
        if self._status not in (ItemStatus.ON_LOAN, ItemStatus.RESERVED):
            raise InvalidStateError("Only a loaned or reserved item can become available.")
        self._status = ItemStatus.AVAILABLE

    def _retire(self) -> None:
        if self._status is ItemStatus.ON_LOAN:
            raise InvalidStateError("Return an item before retiring it.")
        self._status = ItemStatus.RETIRED

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Item) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self._id}, name={self._name!r}, status={self._status.name})"


class AcademicTechItem(Item):
    def __init__(self, name: str, description: str, condition: ItemCondition = ItemCondition.GOOD,
                 accessories: tuple[str, ...] | list[str] = ()) -> None:
        super().__init__(name, description, condition)
        self._accessories = tuple(require_text(value, "accessory") for value in accessories)

    @property
    def accessories(self) -> tuple[str, ...]:
        return self._accessories

    def get_category(self) -> ItemCategory:
        return ItemCategory.ACADEMIC_TECH

    def get_care_instructions(self) -> str:
        if not self._accessories:
            return "Protect from spills and return with any included cables or adapters."
        return "Return with: " + ", ".join(self._accessories)


class DormUtilityItem(Item):
    def __init__(self, name: str, description: str, condition: ItemCondition = ItemCondition.GOOD,
                 safety_instructions: str = "Use according to the manufacturer's instructions.",
                 safety_check_required: bool = False) -> None:
        super().__init__(name, description, condition)
        self._safety_instructions = require_text(safety_instructions, "safety_instructions")
        self._safety_check_required = bool(safety_check_required)

    @property
    def safety_check_required(self) -> bool:
        return self._safety_check_required

    def get_category(self) -> ItemCategory:
        return ItemCategory.DORM_UTILITY

    def get_care_instructions(self) -> str:
        return self._safety_instructions


class SocialLeisureItem(Item):
    def __init__(self, name: str, description: str, condition: ItemCondition = ItemCondition.GOOD,
                 event_use_only: bool = False, group_use_allowed: bool = True) -> None:
        super().__init__(name, description, condition)
        self._event_use_only = bool(event_use_only)
        self._group_use_allowed = bool(group_use_allowed)

    @property
    def event_use_only(self) -> bool:
        return self._event_use_only

    @property
    def group_use_allowed(self) -> bool:
        return self._group_use_allowed

    def get_category(self) -> ItemCategory:
        return ItemCategory.SOCIAL_LEISURE

    def get_care_instructions(self) -> str:
        if self._event_use_only:
            return "Use for campus events and return promptly."
        return "Use considerately and return clean and ready for the next student."
