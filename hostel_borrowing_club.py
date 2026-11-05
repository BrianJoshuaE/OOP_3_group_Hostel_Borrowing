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


<<<<<<< HEAD






























































































































































































































































































































































































































































































































































































































































































































































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
=======
# Warren's part: item types, loan tracking, and loan-history records.
# =====================================================================
# ITEMS - ABSTRACTION + INHERITANCE + POLYMORPHISM
# =====================================================================

class Item(ABC):
    """Abstract item. Subclasses decide their own loan period (POLYMORPHISM)."""

    CATEGORY = "General"        # class-level attribute (overridden by subclasses)
    _id_counter = 0             # shared by ALL items (STATIC MEMBER)

    def __init__(self, name: str, condition: ItemCondition = ItemCondition.GOOD,
                 item_id: Optional[str] = None):
        self._item_id = item_id or Item._next_id()
        self._name = Validator.non_empty(name, "Item name")
        self._condition = ItemCondition.GOOD
        self.condition = condition
        self._status = ItemStatus.AVAILABLE

    @staticmethod
    def _next_id() -> str:
        Item._id_counter += 1
        return f"ITM-{Item._id_counter:03d}"

    # GETTERS / SETTERS
    @property
    def item_id(self) -> str:
        return self._item_id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = Validator.non_empty(value, "Item name")

    @property
    def category(self) -> str:
        return self.CATEGORY

    @property
    def condition(self) -> ItemCondition:
        return self._condition

    @condition.setter
    def condition(self, value: ItemCondition) -> None:
        if not isinstance(value, ItemCondition):
            raise ValidationError("Condition must be an ItemCondition value.")
        self._condition = value

    @property
    def status(self) -> ItemStatus:          # read-only: only lifecycle methods change it
        return self._status

    @abstractmethod
    def loan_period_days(self) -> int:
        """How many days this kind of item may be borrowed."""

    def is_available(self) -> bool:
        return self._status == ItemStatus.AVAILABLE

    # OBJECT LIFECYCLE: available -> on loan -> available / under repair -> retired
    def mark_on_loan(self) -> None:
        if not self.is_available():
            raise ItemUnavailableError(f"'{self._name}' is {self._status.value.lower()}.")
        self._status = ItemStatus.ON_LOAN

    def mark_returned(self, condition: ItemCondition) -> None:
        if self._status != ItemStatus.ON_LOAN:
            raise InvalidStateError(f"'{self._name}' is not on loan.")
        self.condition = condition
        self._status = (ItemStatus.UNDER_REPAIR if condition == ItemCondition.DAMAGED
                        else ItemStatus.AVAILABLE)

    def send_for_repair(self) -> None:
        if self._status != ItemStatus.AVAILABLE:
            raise InvalidStateError("Only an available item can be sent for repair.")
        self._status = ItemStatus.UNDER_REPAIR

    def complete_repair(self, condition: ItemCondition) -> None:
        if self._status != ItemStatus.UNDER_REPAIR:
            raise InvalidStateError(f"'{self._name}' is not under repair.")
        if condition == ItemCondition.DAMAGED:
            raise ValidationError("A repaired item cannot still be DAMAGED.")
        self.condition = condition
        self._status = ItemStatus.AVAILABLE

    def retire(self) -> None:
        if self._status == ItemStatus.ON_LOAN:
            raise InvalidStateError("Cannot retire an item that is on loan.")
        self._status = ItemStatus.RETIRED

    def describe(self) -> str:
        return self._name

    def summary(self) -> str:
        return (f"{self._item_id} | {self.describe()} | {self.category} | "
                f"{self._condition.name} | {self._status.value}")

    # EQUALITY & SORTING
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Item) and self._item_id == other._item_id

    def __hash__(self) -> int:
        return hash(self._item_id)

    def __lt__(self, other: "Item") -> bool:
        return self._item_id < other._item_id

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._item_id!r}, {self._name!r})"


class ElectricalItem(Item):
    CATEGORY = "Electrical"

    def __init__(self, name: str, condition: ItemCondition = ItemCondition.GOOD,
                 item_id: Optional[str] = None, wattage: Optional[int] = None):
        super().__init__(name, condition, item_id)
        self._wattage = wattage

    def loan_period_days(self) -> int:      # POLYMORPHISM
        return 2

    def describe(self) -> str:              # method overriding
        extra = f" ({self._wattage}W)" if self._wattage else ""
        return f"{self._name}{extra}"


class ToolItem(Item):
    CATEGORY = "Tools"

    def loan_period_days(self) -> int:
        return 3


class KitchenItem(Item):
    CATEGORY = "Kitchen"

    def loan_period_days(self) -> int:
        return 1


class AcademicItem(Item):
    CATEGORY = "Academic"

    def loan_period_days(self) -> int:
        return 7


class SportsItem(Item):
    CATEGORY = "Sports"

    def loan_period_days(self) -> int:
        return 2


# =====================================================================
# LOANS - the tracking record
# =====================================================================

@dataclass(frozen=True)
class LoanRecord:
    """IMMUTABLE snapshot of a loan - history can never be edited."""
    loan_id: str
    item_id: str
    item_name: str
    student_id: str
    student_name: str
    address: str
    borrowed_at: datetime
    due_at: datetime
    returned_at: Optional[datetime]
    condition_out: ItemCondition
    condition_in: Optional[ItemCondition]
    issued_by: str
    received_by: Optional[str]
    extensions: int

    @property
    def was_late(self) -> bool:
        return self.returned_at is not None and self.returned_at > self.due_at

    @property
    def returned_damaged(self) -> bool:
        return self.condition_in == ItemCondition.DAMAGED

    def summary(self) -> str:
        if self.returned_at is None:
            state = "STILL OUT"
        else:
            state = f"returned {Clock.fmt(self.returned_at)} as {self.condition_in.name}"
            if self.was_late:
                state += " (LATE)"
        return (f"{self.loan_id} | {self.item_name} | {self.student_name} "
                f"({self.address}) | out {Clock.fmt(self.borrowed_at)} "
                f"as {self.condition_out.name} | due {Clock.fmt(self.due_at)} | {state}")


class Loan:
    """A live loan. COMPOSITION: a Loan holds an Item and a Student."""

    MAX_EXTENSIONS = 1          # class-level rule
    _counter = 0

    def __init__(self, item: Item, student: Student, issued_by: ClubKeeper,
                 borrowed_at: datetime, due_at: datetime):
        Loan._counter += 1
        self._loan_id = f"LN-{Loan._counter:04d}"
        self._item = item
        self._student = student
        self._issued_by = issued_by.name
        self._borrowed_at = borrowed_at
        self._due_at = due_at
        self._condition_out = item.condition        # condition at checkout
        self._returned_at: Optional[datetime] = None
        self._condition_in: Optional[ItemCondition] = None
        self._received_by: Optional[str] = None
        self._extensions = 0

    @property
    def loan_id(self) -> str:
        return self._loan_id

    @property
    def item(self) -> Item:
        return self._item

    @property
    def student(self) -> Student:
        return self._student

    @property
    def borrowed_at(self) -> datetime:
        return self._borrowed_at

    @property
    def due_at(self) -> datetime:
        return self._due_at

    @property
    def is_active(self) -> bool:
        return self._returned_at is None

    def is_overdue(self, now: Optional[datetime] = None) -> bool:
        return self.is_active and (now or Clock.now()) > self._due_at

    def extend(self, extra_days: int) -> None:
        if self._extensions >= Loan.MAX_EXTENSIONS:
            raise ExtensionError("This loan has already been extended once.")
        self._due_at += timedelta(days=extra_days)
        self._extensions += 1

    def close(self, condition: ItemCondition, keeper: ClubKeeper,
              returned_at: datetime) -> None:
        if not self.is_active:
            raise InvalidStateError("This loan is already closed.")
        if returned_at < self._borrowed_at:
            raise ValidationError("Return time cannot be before borrow time.")
        self._returned_at = returned_at
        self._condition_in = condition
        self._received_by = keeper.name

    def to_record(self) -> LoanRecord:
        return LoanRecord(
            self._loan_id, self._item.item_id, self._item.name,
            self._student.person_id, self._student.name, self._student.address,
            self._borrowed_at, self._due_at, self._returned_at,
            self._condition_out, self._condition_in,
            self._issued_by, self._received_by, self._extensions,
        )

    def summary(self, now: Optional[datetime] = None) -> str:
        if not self.is_active:
            flag = f"RETURNED {Clock.fmt(self._returned_at)} as {self._condition_in.name}"
            if self._returned_at > self._due_at:
                flag += " (LATE)"
        else:
            flag = "OVERDUE" if self.is_overdue(now) else "ON TIME"
        return (f"{self._loan_id} | {self._item.name} ({self._item.item_id}) -> "
                f"{self._student.name} ({self._student.address}) | "
                f"out {Clock.fmt(self._borrowed_at)} as {self._condition_out.name} | "
                f"due {Clock.fmt(self._due_at)} | {flag}")


@dataclass(frozen=True)
class UsageStat:
    """One line of a 'most borrowed' or 'most damaged' report."""
    item_id: str
    item_name: str
    count: int
    label: str

    def summary(self) -> str:
        return f"{self.item_name} ({self.item_id}) - {self.label} {self.count}x"

# Warren's contribution ends here: loan records and usage statistics are complete.
# David's borrowing policies and supporting collections begin below.

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
>>>>>>> origin/main
