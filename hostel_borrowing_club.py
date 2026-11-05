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














































































































































































































































































































# David's part: loan policies, inventory/registry/ledger, and report printing.
# =====================================================================
# BORROWING RULES - STRATEGY pattern (swap the policy without changing the club)
# =====================================================================

class LoanPolicy(ABC):
    @abstractmethod
    def max_active_loans(self) -> int:
        """How many items one student may hold at once."""

    @abstractmethod
    def extension_days(self) -> int:
        """How many days a single extension adds."""

    def name(self) -> str:
        return type(self).__name__


class StandardPolicy(LoanPolicy):
    def max_active_loans(self) -> int:
        return 2

    def extension_days(self) -> int:
        return 1


class ExamWeekPolicy(LoanPolicy):
    def max_active_loans(self) -> int:
        return 3

    def extension_days(self) -> int:
        return 2


# =====================================================================
# CONTAINERS - each class has ONE job (Single Responsibility)
# =====================================================================

class Inventory:
    """Holds the club's items."""

    def __init__(self):
        self._items: Dict[str, Item] = {}

    def add(self, item: Item) -> None:
        if item.item_id in self._items:
            raise ValidationError(f"Item {item.item_id} already exists.")
        self._items[item.item_id] = item

    def remove(self, item_id: str) -> Item:
        item = self.get(item_id)
        if item.status == ItemStatus.ON_LOAN:
            raise InvalidStateError("Cannot remove an item that is on loan.")
        return self._items.pop(item_id)

    def get(self, item_id: str) -> Item:
        try:
            return self._items[item_id.strip().upper()]
        except KeyError:
            raise ItemNotFoundError(f"No item with ID '{item_id}'.") from None

    def all(self) -> List[Item]:
        return sorted(self._items.values())

    def by_status(self, status: ItemStatus) -> List[Item]:
        return [i for i in self.all() if i.status == status]

    def search(self, keyword: str) -> List[Item]:
        keyword = keyword.lower()
        return [i for i in self.all() if keyword in i.name.lower()]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self.all())


class StudentRegistry:
    """Holds registered students."""

    def __init__(self):
        self._students: Dict[str, Student] = {}

    def register(self, student: Student) -> None:
        if student.person_id in self._students:
            raise ValidationError(f"Student {student.person_id} is already registered.")
        self._students[student.person_id] = student

    def get(self, student_id: str) -> Student:
        try:
            return self._students[student_id.strip()]
        except KeyError:
            raise NotRegisteredError(f"Student '{student_id}' is not registered.") from None

    def all(self) -> List[Student]:
        return sorted(self._students.values())

    def __len__(self) -> int:
        return len(self._students)


class WaitingList:
    """Queue of students waiting for an item that is currently unavailable."""

    def __init__(self):
        self._queues: Dict[str, List[Student]] = {}

    def join(self, item: Item, student: Student) -> None:
        queue = self._queues.setdefault(item.item_id, [])
        if student in queue:
            raise ValidationError(f"{student.name} is already waiting for {item.name}.")
        queue.append(student)

    def leave(self, item: Item, student: Student) -> None:
        queue = self._queues.get(item.item_id, [])
        if student in queue:
            queue.remove(student)

    def waiting_for(self, item: Item) -> List[Student]:
        return list(self._queues.get(item.item_id, []))

    def next_in_line(self, item: Item) -> Optional[Student]:
        queue = self._queues.get(item.item_id, [])
        return queue[0] if queue else None


class LoanLedger:
    """Stores active loans and the immutable history of closed ones."""

    def __init__(self):
        self._active: Dict[str, Loan] = {}          # item_id -> live Loan
        self._closed: List[LoanRecord] = []         # never modified after being added

    def open_loan(self, loan: Loan) -> None:
        self._active[loan.item.item_id] = loan

    def close_loan(self, loan: Loan) -> None:
        del self._active[loan.item.item_id]
        self._closed.append(loan.to_record())

    def active_loan_for(self, item_id: str) -> Optional[Loan]:
        return self._active.get(item_id)

    def active_loans(self) -> List[Loan]:
        return sorted(self._active.values(), key=lambda l: l.borrowed_at)

    def active_loans_of(self, student_id: str) -> List[Loan]:
        return [l for l in self.active_loans() if l.student.person_id == student_id]

    def overdue_loans(self, now: datetime) -> List[Loan]:
        return [l for l in self.active_loans() if l.is_overdue(now)]

    def overdue_loans_of(self, student_id: str, now: datetime) -> List[Loan]:
        return [l for l in self.overdue_loans(now) if l.student.person_id == student_id]

    def all_records(self) -> List[LoanRecord]:
        live = [l.to_record() for l in self._active.values()]
        return sorted(self._closed + live, key=lambda r: r.borrowed_at)

    # OVERLOADING: one method name, behaviour chosen by the argument's type
    @singledispatchmethod
    def history_of(self, target) -> List[LoanRecord]:
        raise TypeError("history_of expects a Student or an Item.")

    @history_of.register(Student)
    def _(self, target: Student) -> List[LoanRecord]:
        return [r for r in self.all_records() if r.student_id == target.person_id]

    @history_of.register(Item)
    def _(self, target: Item) -> List[LoanRecord]:
        return [r for r in self.all_records() if r.item_id == target.item_id]

    def most_borrowed(self, top: int = 3) -> List[UsageStat]:
        counts = Counter((r.item_id, r.item_name) for r in self.all_records())
        return [UsageStat(i, n, c, "borrowed") for (i, n), c in counts.most_common(top)]

    def most_damaged(self, top: int = 3) -> List[UsageStat]:
        counts = Counter((r.item_id, r.item_name)
                         for r in self.all_records() if r.returned_damaged)
        return [UsageStat(i, n, c, "returned damaged") for (i, n), c in counts.most_common(top)]








































































































































































































# David's part continues: the duck-typed report printer.
# =====================================================================
# REPORT PRINTER - DUCK TYPING in action
# =====================================================================

class ReportPrinter:
    """
    Prints anything that has a summary() method. Items, Loans, LoanRecords,
    Students and UsageStats share NO common parent - they only share the
    behaviour "I can summarise myself". That is duck typing.
    """

    @staticmethod
    def show(title: str, things) -> None:
        print(f"\n--- {title} ---")
        things = list(things)
        if not things:
            print("  (none)")
        for number, thing in enumerate(things, start=1):
            print(f"  {number}. {thing.summary()}")