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





































































































































































































































































































































































































































































































# Ninsiima's part: the main club operations and sample data.
# =====================================================================
# THE CLUB - COMPOSITION: it creates and owns its parts;
#            AGGREGATION: it holds references to keepers it did not create.
# =====================================================================

class HostelBorrowingClub:
    def __init__(self, name: str, policy: Optional[LoanPolicy] = None):
        self._name = Validator.non_empty(name, "Club name")
        self._policy: LoanPolicy = policy or StandardPolicy()
        # composition: these parts live and die with the club
        self._inventory = Inventory()
        self._students = StudentRegistry()
        self._ledger = LoanLedger()
        self._waiting = WaitingList()
        # aggregation: keepers exist independently of the club
        self._keepers: Dict[str, ClubKeeper] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def policy(self) -> LoanPolicy:
        return self._policy

    @policy.setter
    def policy(self, value: LoanPolicy) -> None:
        if not isinstance(value, LoanPolicy):
            raise ValidationError("Policy must be a LoanPolicy.")
        self._policy = value

    @property
    def inventory(self) -> Inventory:
        return self._inventory

    @property
    def students(self) -> StudentRegistry:
        return self._students

    @property
    def ledger(self) -> LoanLedger:
        return self._ledger

    @property
    def waiting_list(self) -> WaitingList:
        return self._waiting

    # ---------------- access control (DUCK TYPING) ----------------
    def appoint_keeper(self, keeper: ClubKeeper) -> None:
        self._keepers[keeper.person_id] = keeper

    def _require(self, keeper, action: str) -> None:
        """Accepts ANY object that has can() - no isinstance check needed."""
        can = getattr(keeper, "can", None)
        who = getattr(keeper, "name", "Unknown")
        if not callable(can) or not can(action):
            raise PermissionDeniedError(f"{who} is not allowed to perform '{action}'.")
        if getattr(keeper, "person_id", None) not in self._keepers:
            raise PermissionDeniedError(f"{who} is not an appointed keeper of this club.")

    # ---------------- administration ----------------
    def register_student(self, keeper, student: Student) -> None:
        self._require(keeper, "register_student")
        self._students.register(student)

    def add_item(self, keeper, item: Item) -> None:
        self._require(keeper, "add_item")
        self._inventory.add(item)

    def remove_item(self, keeper, item_id: str) -> Item:
        self._require(keeper, "remove_item")
        return self._inventory.remove(item_id)

    def send_for_repair(self, keeper, item_id: str) -> None:
        self._require(keeper, "manage_repairs")
        self._inventory.get(item_id).send_for_repair()

    def complete_repair(self, keeper, item_id: str, condition: ItemCondition) -> None:
        self._require(keeper, "manage_repairs")
        self._inventory.get(item_id).complete_repair(condition)

    def retire_item(self, keeper, item_id: str) -> None:
        self._require(keeper, "manage_repairs")
        self._inventory.get(item_id).retire()

    # ---------------- borrowing (rules are hidden here: ABSTRACTION) ----------------
    def borrow_item(self, keeper, student_id: str, item_id: str,
                    now: Optional[datetime] = None) -> Loan:
        self._require(keeper, "issue_loan")
        now = now or Clock.now()
        student = self._students.get(student_id)
        item = self._inventory.get(item_id)

        if not item.is_available():
            raise ItemUnavailableError(f"'{item.name}' is {item.status.value.lower()}.")

        first = self._waiting.next_in_line(item)
        if first is not None and first != student:
            raise ItemUnavailableError(
                f"'{item.name}' is reserved for {first.name}, who is first in the waiting list.")

        if self._ledger.overdue_loans_of(student.person_id, now):
            raise OverdueBlockError(f"{student.name} has overdue items and must return them first.")

        limit = self._policy.max_active_loans()
        if len(self._ledger.active_loans_of(student.person_id)) >= limit:
            raise BorrowLimitError(f"{student.name} already holds {limit} items (limit under {self._policy.name()}).")

        due = now + timedelta(days=item.loan_period_days())    # polymorphic call
        loan = Loan(item, student, keeper, now, due)
        item.mark_on_loan()
        self._ledger.open_loan(loan)
        self._waiting.leave(item, student)
        return loan

    def return_item(self, keeper, item_id: str, condition: ItemCondition,
                    now: Optional[datetime] = None) -> Loan:
        self._require(keeper, "receive_return")
        now = now or Clock.now()
        item = self._inventory.get(item_id)
        loan = self._ledger.active_loan_for(item.item_id)
        if loan is None:
            raise LoanNotFoundError(f"'{item.name}' is not currently on loan.")
        loan.close(condition, keeper, now)
        item.mark_returned(condition)
        self._ledger.close_loan(loan)
        return loan

    def extend_loan(self, keeper, item_id: str, now: Optional[datetime] = None) -> Loan:
        self._require(keeper, "extend_loan")
        now = now or Clock.now()
        item = self._inventory.get(item_id)
        loan = self._ledger.active_loan_for(item.item_id)
        if loan is None:
            raise LoanNotFoundError(f"'{item.name}' is not currently on loan.")
        if loan.is_overdue(now):
            raise ExtensionError("An overdue loan cannot be extended.")
        waiting = self._waiting.waiting_for(item)
        if waiting:
            raise ExtensionError(f"Cannot extend: {waiting[0].name} is waiting for this item.")
        loan.extend(self._policy.extension_days())
        return loan

    def join_waiting_list(self, keeper, student_id: str, item_id: str) -> None:
        self._require(keeper, "manage_waitlist")
        student = self._students.get(student_id)
        item = self._inventory.get(item_id)
        if item.is_available() and not self._waiting.waiting_for(item):
            raise InvalidStateError(f"'{item.name}' is available - borrow it directly.")
        if item.status == ItemStatus.RETIRED:
            raise InvalidStateError(f"'{item.name}' has been retired.")
        self._waiting.join(item, student)

    # ---------------- reports ----------------
    def availability_of(self, item_id: str, now: Optional[datetime] = None) -> str:
        now = now or Clock.now()
        item = self._inventory.get(item_id)
        if item.is_available():
            return f"{item.name} is AVAILABLE (condition: {item.condition.name})."
        loan = self._ledger.active_loan_for(item.item_id)
        if loan:
            late = " It is OVERDUE." if loan.is_overdue(now) else ""
            return (f"{item.name} is ON LOAN to {loan.student.name} "
                    f"({loan.student.address}) until {Clock.fmt(loan.due_at)}.{late}")
        return f"{item.name} is {item.status.value.upper()} (condition: {item.condition.name})."

    def available_items(self) -> List[Item]:
        return self._inventory.by_status(ItemStatus.AVAILABLE)

    def all_items(self) -> List[Item]:
        return self._inventory.all()

    def items_needing_attention(self) -> List[Item]:
        return (self._inventory.by_status(ItemStatus.UNDER_REPAIR)
                + self._inventory.by_status(ItemStatus.RETIRED))

    def borrowed_loans(self) -> List[Loan]:
        return self._ledger.active_loans()

    def overdue_loans(self, now: Optional[datetime] = None) -> List[Loan]:
        return self._ledger.overdue_loans(now or Clock.now())

    def history_of_student(self, student_id: str) -> List[LoanRecord]:
        return self._ledger.history_of(self._students.get(student_id))

    def history_of_item(self, item_id: str) -> List[LoanRecord]:
        return self._ledger.history_of(self._inventory.get(item_id))

    def most_borrowed(self, top: int = 3) -> List[UsageStat]:
        return self._ledger.most_borrowed(top)

    def most_damaged(self, top: int = 3) -> List[UsageStat]:
        return self._ledger.most_damaged(top)

# Ninsiima's club-operations section ends here.
# David's report-printer section follows, then Ninsiima's sample-data section.

# Ninsiima's part continues: the sample data.
# =====================================================================
# SAMPLE DATA
# =====================================================================

def build_sample_club() -> Tuple[HostelBorrowingClub, ClubKeeper]:
    club = HostelBorrowingClub("Greenview Hostel Borrowing Club", StandardPolicy())
    keeper = ClubKeeper("K-01", "Grace Mwangi", "1234")
    club.appoint_keeper(keeper)

    for student in (
        Student("S001", "Alice Njeri", "B-204", "Block B", "0712345678"),
        Student("S002", "Bob Otieno", "A-110", "Block A", "0723456789"),
        Student("S003", "Carol Wanjiru", "C-305", "Block C", "0734567890"),
    ):
        club.register_student(keeper, student)

    for item in (
        ElectricalItem("Steam Iron", wattage=1200),
        ElectricalItem("Extension Cord"),
        ToolItem("Toolkit"),
        KitchenItem("Hot Pot"),
        AcademicItem("Scientific Calculator"),
        SportsItem("Football", ItemCondition.FAIR),
    ):
        club.add_item(keeper, item)
    return club, keeper

# Ninsiima's contribution ends here: the sample club and its data are defined.
# Akankwasa's guided demo, interactive menu, and entry point begin below.