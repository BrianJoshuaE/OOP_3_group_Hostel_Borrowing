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
































































































































































































































































































































































































































































































































































































































































































































































# Akankwasa's part: the guided demo, interactive menu, and program entry point.
# =====================================================================
# GUIDED DEMO
# =====================================================================

def attempt(description: str, action) -> None:
    """Run an action and show either its result or the rule that blocked it."""
    try:
        result = action()
        print(f"  OK      {description}")
        if hasattr(result, "summary"):
            print(f"          {result.summary()}")
    except ClubError as error:
        print(f"  BLOCKED {description}\n          -> {type(error).__name__}: {error}")


def run_demo() -> None:
    print("=" * 70)
    print(" HOSTEL BORROWING CLUB - GUIDED DEMO")
    print("=" * 70)

    club, grace = build_sample_club()
    print(f"\nClub: {club.name} | Keeper: {grace.name} | Policy: {club.policy.name()}")

    items = {i.name: i for i in club.all_items()}
    iron, toolkit, hot_pot = items["Steam Iron"], items["Toolkit"], items["Hot Pot"]
    calculator, football = items["Scientific Calculator"], items["Football"]
    cord = items["Extension Cord"]

    t0 = Clock.now().replace(second=0)
    Clock.set_fixed(t0)
    ReportPrinter.show("Registered students", club.students.all())
    ReportPrinter.show("All items", club.all_items())

    print("\n>>> Day 0: borrowing")
    attempt("Alice borrows the iron", lambda: club.borrow_item(grace, "S001", iron.item_id, t0))
    attempt("Alice borrows the toolkit", lambda: club.borrow_item(grace, "S001", toolkit.item_id, t0))
    attempt("Bob borrows the hot pot", lambda: club.borrow_item(grace, "S002", hot_pot.item_id, t0))
    attempt("Carol borrows the iron (taken)", lambda: club.borrow_item(grace, "S003", iron.item_id, t0))
    attempt("Alice borrows a 3rd item (limit is 2)", lambda: club.borrow_item(grace, "S001", calculator.item_id, t0))
    attempt("Unknown student S999 borrows the cord", lambda: club.borrow_item(grace, "S999", cord.item_id, t0))
    alice = club.students.get("S001")
    attempt("Alice tries to act as keeper", lambda: club.borrow_item(alice, "S001", cord.item_id, t0))

    ReportPrinter.show("Available items", club.available_items())
    ReportPrinter.show("Currently borrowed", club.borrowed_loans())
    print("\nAvailability check:", club.availability_of(iron.item_id, t0))

    print("\n>>> Day 0 (4 hours later): extensions and waiting list")
    later = t0 + timedelta(hours=4)
    Clock.set_fixed(later)
    attempt("Alice extends the iron (first time)", lambda: club.extend_loan(grace, iron.item_id, later))
    attempt("Alice extends the iron again", lambda: club.extend_loan(grace, iron.item_id, later))
    attempt("Carol joins the waiting list for the toolkit",
            lambda: club.join_waiting_list(grace, "S003", toolkit.item_id))
    attempt("Alice extends the toolkit (Carol is waiting)",
            lambda: club.extend_loan(grace, toolkit.item_id, later))

    print("\n>>> Day 5: items are overdue")
    day5 = t0 + timedelta(days=5)
    Clock.set_fixed(day5)
    ReportPrinter.show("Overdue loans", club.overdue_loans(day5))
    attempt("Alice (overdue) tries to borrow the calculator",
            lambda: club.borrow_item(grace, "S001", calculator.item_id, day5))

    print("\n>>> Day 5: returns")
    attempt("Alice returns the iron (GOOD)", lambda: club.return_item(grace, iron.item_id, ItemCondition.GOOD, day5))
    attempt("Alice returns the toolkit (DAMAGED)", lambda: club.return_item(grace, toolkit.item_id, ItemCondition.DAMAGED, day5))
    attempt("Bob returns the hot pot (FAIR)", lambda: club.return_item(grace, hot_pot.item_id, ItemCondition.FAIR, day5))
    attempt("Bob returns the hot pot again", lambda: club.return_item(grace, hot_pot.item_id, ItemCondition.FAIR, day5))
    ReportPrinter.show("Items needing attention", club.items_needing_attention())

    print("\n>>> Day 6: repair and fair queueing")
    day6 = t0 + timedelta(days=6)
    Clock.set_fixed(day6)
    attempt("Keeper repairs the toolkit", lambda: club.complete_repair(grace, toolkit.item_id, ItemCondition.GOOD))
    attempt("Bob joins the toolkit waiting list (after Carol)",
            lambda: club.join_waiting_list(grace, "S002", toolkit.item_id))
    attempt("Bob tries to borrow the toolkit (Carol is first)",
            lambda: club.borrow_item(grace, "S002", toolkit.item_id, day6))
    attempt("Carol borrows the toolkit", lambda: club.borrow_item(grace, "S003", toolkit.item_id, day6))
    attempt("Keeper retires the football", lambda: club.retire_item(grace, football.item_id))
    attempt("Someone borrows the retired football", lambda: club.borrow_item(grace, "S002", football.item_id, day6))

    print("\n>>> Reports")
    ReportPrinter.show("History of Alice", club.history_of_student("S001"))
    ReportPrinter.show("History of the toolkit", club.history_of_item(toolkit.item_id))
    ReportPrinter.show("Most borrowed items", club.most_borrowed())
    ReportPrinter.show("Most often returned damaged", club.most_damaged())
    ReportPrinter.show("Final status of every item", club.all_items())
    print("\nAvailability check:", club.availability_of(toolkit.item_id, day6))
    print("Availability check:", club.availability_of(football.item_id, day6))

    print("\n>>> Swapping the policy (Strategy pattern)")
    club.policy = ExamWeekPolicy()
    print(f"Policy is now {club.policy.name()}: "
          f"max {club.policy.max_active_loans()} items per student.")
    Clock.set_fixed(None)       # back to the real clock


# =====================================================================
# INTERACTIVE MENU (kept separate from the club logic)
# =====================================================================

class ConsoleApp:
    CATEGORY_CLASSES = {
        "1": ElectricalItem, "2": ToolItem, "3": KitchenItem,
        "4": AcademicItem, "5": SportsItem,
    }

    def __init__(self, club: HostelBorrowingClub, keeper: ClubKeeper):
        self._club = club
        self._keeper = keeper

    @staticmethod
    def _ask(prompt: str) -> str:
        return input(f"{prompt}: ").strip()

    def _ask_condition(self) -> ItemCondition:
        options = list(ItemCondition)
        for number, cond in enumerate(options, start=1):
            print(f"   {number}. {cond.name}")
        choice = self._ask("Condition number")
        if not choice.isdigit() or not 1 <= int(choice) <= len(options):
            raise ValidationError("Please choose a valid condition number.")
        return options[int(choice) - 1]

    def _login(self) -> bool:
        print(f"Keeper login: {self._keeper.name} (demo PIN is 1234)")
        for _ in range(3):
            if self._keeper.verify_pin(self._ask("Enter PIN")):
                print("Welcome!\n")
                return True
            print("Wrong PIN.")
        print("Too many attempts.")
        return False

    def run(self) -> None:
        menu = [
            ("Show available items", self._available),
            ("Show all items and their condition", self._all_items),
            ("Check one item's availability", self._check_item),
            ("Borrow an item", self._borrow),
            ("Return an item", self._return),
            ("Extend a loan", self._extend),
            ("Show borrowed items", self._borrowed),
            ("Show overdue items", self._overdue),
            ("Borrowing history (student or item)", self._history),
            ("Most borrowed / most damaged", self._stats),
            ("Register a student", self._register),
            ("Add an item", self._add_item),
            ("Join an item's waiting list", self._waitlist),
        ]
        try:
            if not self._login():
                return
            while True:
                print(f"=== {self._club.name} ===")
                for number, (label, _) in enumerate(menu, start=1):
                    print(f" {number:>2}. {label}")
                print("  0. Exit")
                choice = self._ask("Choose")
                if choice == "0":
                    break
                if not choice.isdigit() or not 1 <= int(choice) <= len(menu):
                    print("Invalid choice.\n")
                    continue
                try:
                    menu[int(choice) - 1][1]()
                except ClubError as error:
                    print(f"\n  ! {error}")
                print()
        except (EOFError, KeyboardInterrupt):
            print()
        print("Goodbye!")

    # --- menu actions
    def _available(self):
        ReportPrinter.show("Available items", self._club.available_items())

    def _all_items(self):
        ReportPrinter.show("All items", self._club.all_items())

    def _check_item(self):
        print(" ", self._club.availability_of(self._ask("Item ID (e.g. ITM-001)")))

    def _borrow(self):
        loan = self._club.borrow_item(self._keeper, self._ask("Student ID"),
                                      self._ask("Item ID"))
        print("\n  Loan recorded:\n ", loan.summary())

    def _return(self):
        item_id = self._ask("Item ID")
        loan = self._club.return_item(self._keeper, item_id, self._ask_condition())
        print("\n  Return recorded:\n ", loan.to_record().summary())

    def _extend(self):
        loan = self._club.extend_loan(self._keeper, self._ask("Item ID"))
        print("\n  Extended:\n ", loan.summary())

    def _borrowed(self):
        ReportPrinter.show("Currently borrowed", self._club.borrowed_loans())

    def _overdue(self):
        ReportPrinter.show("Overdue items", self._club.overdue_loans())

    def _history(self):
        kind = self._ask("History of a (s)tudent or an (i)tem").lower()
        if kind.startswith("s"):
            ReportPrinter.show("Student history", self._club.history_of_student(self._ask("Student ID")))
        else:
            ReportPrinter.show("Item history", self._club.history_of_item(self._ask("Item ID")))

    def _stats(self):
        ReportPrinter.show("Most borrowed", self._club.most_borrowed())
        ReportPrinter.show("Most often returned damaged", self._club.most_damaged())

    def _register(self):
        student = Student(self._ask("Student ID"), self._ask("Full name"),
                          self._ask("Room number (e.g. B-204)"),
                          self._ask("Block (e.g. Block B)"), self._ask("Phone"))
        self._club.register_student(self._keeper, student)
        print("  Registered:", student.summary())

    def _add_item(self):
        print("  1.Electrical 2.Tools 3.Kitchen 4.Academic 5.Sports")
        cls = self.CATEGORY_CLASSES.get(self._ask("Category number"))
        if cls is None:
            raise ValidationError("Please choose a category from 1 to 5.")
        item = cls(self._ask("Item name"))
        self._club.add_item(self._keeper, item)
        print("  Added:", item.summary())

    def _waitlist(self):
        self._club.join_waiting_list(self._keeper, self._ask("Student ID"), self._ask("Item ID"))
        print("  Added to the waiting list.")


# =====================================================================
# ENTRY POINT
# =====================================================================

def main() -> None:
    args = sys.argv[1:]
    if "--demo" in args:
        run_demo()
        return
    if "--menu" in args:
        ConsoleApp(*build_sample_club()).run()
        return

    print("Hostel Borrowing Club")
    print("  1. Run the guided demo")
    print("  2. Use the interactive menu")
    try:
        choice = input("Choose 1 or 2: ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if choice == "2":
        ConsoleApp(*build_sample_club()).run()
    else:
        run_demo()


if __name__ == "__main__":
    main()

# Akankwasa's contribution ends here: the program entry point is complete.