"""
Hostel Borrowing Club - an OOP program that tracks borrowing in a hostel.

Run it in VS Code (Python 3.8+, no extra packages):
    python hostel_borrowing_club.py            -> asks you to pick demo or menu
    python hostel_borrowing_club.py --demo     -> guided demo
    python hostel_borrowing_club.py --menu     -> interactive menu (keeper PIN: 1234)

OOP concepts used (search for the labels in the comments):
    ENUMS, EXCEPTIONS, ENCAPSULATION, GETTERS/SETTERS, CONSTRUCTORS,
    ABSTRACTION, INHERITANCE, POLYMORPHISM, DUCK TYPING, COMPOSITION,
    AGGREGATION, STRATEGY, STATIC/CLASS MEMBERS, IMMUTABILITY,
    OVERLOADING (singledispatch), EQUALITY/SORTING, ROLE-BASED ACCESS.
"""

from __future__ import annotations

import re
import sys
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import singledispatchmethod
from typing import Dict, List, Optional, Tuple

# Brian's part: enums, errors, validation, people, and student/keeper classes.
# =====================================================================
# ENUMS - fixed sets of allowed values
# =====================================================================

class ItemStatus(Enum):
    AVAILABLE = "Available"
    ON_LOAN = "On loan"
    UNDER_REPAIR = "Under repair"
    RETIRED = "Retired"


class ItemCondition(Enum):
    NEW = 4
    GOOD = 3
    FAIR = 2
    POOR = 1
    DAMAGED = 0


# =====================================================================
# EXCEPTIONS - one base class, many specific errors
# =====================================================================

class ClubError(Exception):
    """Base class for every error raised by the club."""


class ValidationError(ClubError):
    pass


class PermissionDeniedError(ClubError):
    pass


class NotRegisteredError(ClubError):
    pass


class ItemNotFoundError(ClubError):
    pass


class ItemUnavailableError(ClubError):
    pass


class BorrowLimitError(ClubError):
    pass


class OverdueBlockError(ClubError):
    pass


class LoanNotFoundError(ClubError):
    pass


class ExtensionError(ClubError):
    pass


class InvalidStateError(ClubError):
    pass


# =====================================================================
# UTILITIES - static helper classes (STATIC MEMBERS)
# =====================================================================

class Clock:
    """Date and time helpers. The time can be fixed so the demo can simulate days passing."""

    _fixed: Optional[datetime] = None       # class-level state

    @classmethod
    def set_fixed(cls, moment: Optional[datetime]) -> None:
        cls._fixed = moment

    @classmethod
    def now(cls) -> datetime:
        return cls._fixed or datetime.now().replace(microsecond=0)

    @staticmethod
    def fmt(moment: Optional[datetime]) -> str:
        return moment.strftime("%d %b %Y %H:%M") if moment else "-"


class Validator:
    """Reusable input validation rules."""

    _ROOM = re.compile(r"^[A-Za-z]{0,2}-?\d{1,4}[A-Za-z]?$")
    _PHONE = re.compile(r"^\+?\d{9,15}$")

    @staticmethod
    def non_empty(value: str, field: str) -> str:
        if value is None or not str(value).strip():
            raise ValidationError(f"{field} cannot be empty.")
        return str(value).strip()

    @classmethod
    def room(cls, value: str) -> str:
        value = cls.non_empty(value, "Room number").upper()
        if not cls._ROOM.match(value):
            raise ValidationError(f"'{value}' is not a valid room number (e.g. B-204).")
        return value

    @classmethod
    def phone(cls, value: str) -> str:
        value = cls.non_empty(value, "Phone").replace(" ", "")
        if not cls._PHONE.match(value):
            raise ValidationError("Phone must have 9-15 digits (optional leading +).")
        return value


# =====================================================================
# PEOPLE - ABSTRACTION + INHERITANCE
# =====================================================================

class Person(ABC):
    """Abstract base class: cannot be instantiated directly."""

    def __init__(self, person_id: str, name: str):          # CONSTRUCTOR
        self._person_id = Validator.non_empty(person_id, "ID")
        self._name = Validator.non_empty(name, "Name")

    # GETTERS / SETTERS (properties)
    @property
    def person_id(self) -> str:
        return self._person_id                              # read-only

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = Validator.non_empty(value, "Name")

    @abstractmethod
    def role(self) -> str:
        """Every subclass must say what role it plays."""

    def summary(self) -> str:
        return f"{self.role()}: {self._name} ({self._person_id})"

    # EQUALITY & SORTING
    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Person)
            and type(self) is type(other)
            and self._person_id == other._person_id
        )

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._person_id))

    def __lt__(self, other: "Person") -> bool:
        return self._name.lower() < other._name.lower()

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._person_id!r}, {self._name!r})"


class Student(Person):
    """A hostel resident who can borrow items."""

    def __init__(self, student_id: str, name: str, room_number: str,
                 block: str, phone: str):
        super().__init__(student_id, name)
        self.room_number = room_number      # goes through the validating setter
        self.block = block
        self.phone = phone

    @property
    def room_number(self) -> str:
        return self._room_number

    @room_number.setter
    def room_number(self, value: str) -> None:
        self._room_number = Validator.room(value)

    @property
    def block(self) -> str:
        return self._block

    @block.setter
    def block(self, value: str) -> None:
        self._block = Validator.non_empty(value, "Block")

    @property
    def phone(self) -> str:
        return self._phone

    @phone.setter
    def phone(self, value: str) -> None:
        self._phone = Validator.phone(value)

    @property
    def address(self) -> str:
        return f"{self._block}, Room {self._room_number}"

    def role(self) -> str:                  # method overriding
        return "Student"

    def summary(self) -> str:               # method overriding (extends parent)
        return f"{super().summary()} | {self.address} | {self._phone}"


class ClubKeeper(Person):
    """The student librarian who runs the storeroom (ROLE-BASED ACCESS)."""

    _PERMISSIONS = frozenset({
        "register_student", "add_item", "remove_item", "issue_loan",
        "receive_return", "extend_loan", "manage_repairs", "manage_waitlist",
    })

    def __init__(self, keeper_id: str, name: str, pin: str):
        super().__init__(keeper_id, name)
        self.__pin = self._check_pin(pin)   # double underscore = name-mangled (private)
        self._on_duty = True

    @staticmethod
    def _check_pin(pin: str) -> str:
        if not re.fullmatch(r"\d{4}", str(pin)):
            raise ValidationError("PIN must be exactly 4 digits.")
        return str(pin)

    def verify_pin(self, pin: str) -> bool:
        return str(pin) == self.__pin

    def change_pin(self, old_pin: str, new_pin: str) -> None:
        if not self.verify_pin(old_pin):
            raise PermissionDeniedError("Old PIN is incorrect.")
        self.__pin = self._check_pin(new_pin)

    @property
    def on_duty(self) -> bool:
        return self._on_duty

    @on_duty.setter
    def on_duty(self, value: bool) -> None:
        self._on_duty = bool(value)

    def can(self, action: str) -> bool:
        return self._on_duty and action in self._PERMISSIONS

    def role(self) -> str:
        return "Club Keeper"

# Brian's contribution ends here: the ClubKeeper class is complete.
# Warren's item and loan sections begin below.