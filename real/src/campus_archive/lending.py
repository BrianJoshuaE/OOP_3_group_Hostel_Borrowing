from __future__ import annotations

from datetime import date, datetime
from typing import Callable
from uuid import UUID, uuid4

from .enums import ItemCategory, ItemCondition, ItemStatus, ReservationStatus
from .exceptions import (
    AuthorizationError,
    InvalidStateError,
    ItemUnavailableError,
    NotMemberError,
    OverdueLoansError,
    ReservationRequiredError,
)
from .items import Item
from .policies import AcademicLoanPolicy, EventLoanPolicy, LoanPolicy, UtilityLoanPolicy
from .students import Student
from .validation import require_text


# Liron's contribution: immutable loan facts, reservation lifecycle, and lending rules.
class Loan:
    def __init__(self, borrower: Student, item: Item, borrowed_on: date, due_on: date) -> None:
        if due_on < borrowed_on:
            raise ValueError("due_on cannot precede borrowed_on.")
        self._id: UUID = uuid4()
        self._borrower = borrower
        self._item = item
        self._borrowed_on = borrowed_on
        self._due_on = due_on
        self._condition_on_checkout = item.condition
        self._returned_on: date | None = None
        self._condition_on_return: ItemCondition | None = None

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def borrower(self) -> Student:
        return self._borrower

    @property
    def item(self) -> Item:
        return self._item

    @property
    def borrowed_on(self) -> date:
        return self._borrowed_on

    @property
    def due_on(self) -> date:
        return self._due_on

    @property
    def returned_on(self) -> date | None:
        return self._returned_on

    @property
    def condition_on_checkout(self) -> ItemCondition:
        return self._condition_on_checkout

    @property
    def condition_on_return(self) -> ItemCondition | None:
        return self._condition_on_return

    @property
    def is_returned(self) -> bool:
        return self._returned_on is not None

    def is_overdue(self, today: date) -> bool:
        return not self.is_returned and today > self._due_on

    def _close(self, returned_on: date, condition: ItemCondition) -> None:
        if self.is_returned:
            raise InvalidStateError("This loan has already been returned.")
        if not isinstance(returned_on, date) or isinstance(returned_on, datetime):
            raise TypeError("returned_on must be a date, not a datetime.")
        if not isinstance(condition, ItemCondition):
            raise TypeError("condition must be an ItemCondition.")
        if returned_on < self._borrowed_on:
            raise InvalidStateError("Return date cannot precede checkout.")
        self._returned_on = returned_on
        self._condition_on_return = condition


class Reservation:
    def __init__(self, student: Student, item: Item, reserved_for: date, requested_on: datetime) -> None:
        if reserved_for < requested_on.date():
            raise ValueError("reserved_for cannot be in the past.")
        self._id = uuid4()
        self._student = student
        self._item = item
        self._reserved_for = reserved_for
        self._requested_on = requested_on
        self._status = ReservationStatus.ACTIVE

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def student(self) -> Student:
        return self._student

    @property
    def item(self) -> Item:
        return self._item

    @property
    def reserved_for(self) -> date:
        return self._reserved_for

    @property
    def requested_on(self) -> datetime:
        return self._requested_on

    @property
    def status(self) -> ReservationStatus:
        return self._status

    def _cancel(self) -> None:
        self._require_active()
        self._status = ReservationStatus.CANCELLED

    def _fulfill(self) -> None:
        self._require_active()
        self._status = ReservationStatus.FULFILLED

    def _expire(self) -> None:
        self._require_active()
        self._status = ReservationStatus.EXPIRED

    def _require_active(self) -> None:
        if self._status is not ReservationStatus.ACTIVE:
            raise InvalidStateError("Reservation is no longer active.")


class SignOutLog:
    def __init__(self, privacy_policy: object) -> None:
        self._loans: list[Loan] = []
        self._privacy_policy = privacy_policy

    def _record(self, loan: Loan) -> None:
        self._loans.append(loan)

    def contains(self, loan: Loan) -> bool:
        return loan in self._loans

    def find_active_loans(self, requester: Student) -> list[Loan]:
        if not self._privacy_policy.is_registered(requester):
            raise AuthorizationError("Requester must be a registered student.")
        can_view = getattr(self._privacy_policy, "can_view_loan_details")
        return [loan for loan in self._loans if not loan.is_returned and can_view(requester, loan)]

    def find_overdue(self, requester: Student, today: date) -> list[Loan]:
        if not self._privacy_policy.can_view_overdue_details(requester):
            raise AuthorizationError("Only coordinators may view overdue loan details.")
        return [loan for loan in self._loans if loan.is_overdue(today)]

    def has_overdue_loans(self, student: Student, today: date) -> bool:
        return any(loan.borrower == student and loan.is_overdue(today) for loan in self._loans)

    def sort_by_due_date(self, loans: list[Loan] | None = None) -> list[Loan]:
        return sorted(loans if loans is not None else self._loans, key=lambda loan: loan.due_on)

    def search_by_student_id(self, student_id: str, requester: Student) -> list[Loan]:
        if not self._privacy_policy.can_view_all_loan_details(requester):
            raise AuthorizationError("Only coordinators may search loan history by student ID.")
        student_id = require_text(student_id, "student_id")
        return [loan for loan in self._loans if loan.borrower.student_id == student_id]

    def _purge_expired(self, today: date, retention_days: int) -> int:
        if retention_days < 0:
            raise ValueError("retention_days cannot be negative.")
        cutoff = date.fromordinal(today.toordinal() - retention_days)
        retained = [loan for loan in self._loans
                    if loan.returned_on is None or loan.returned_on >= cutoff]
        removed = len(self._loans) - len(retained)
        self._loans = retained
        return removed

    def _all_loans(self) -> tuple[Loan, ...]:
        return tuple(self._loans)


class LendingService:
    def __init__(
        self,
        members: dict[str, Student],
        sign_out_log: SignOutLog,
        now: Callable[[], datetime],
    ) -> None:
        self._members = members
        self._sign_out_log = sign_out_log
        self._now = now
        self._policies: dict[ItemCategory, LoanPolicy] = {
            ItemCategory.ACADEMIC_TECH: AcademicLoanPolicy(),
            ItemCategory.DORM_UTILITY: UtilityLoanPolicy(),
            ItemCategory.SOCIAL_LEISURE: EventLoanPolicy(),
        }
        self._reservations: list[Reservation] = []

    @property
    def reservations(self) -> tuple[Reservation, ...]:
        return tuple(self._reservations)

    def check_out(self, student: Student, item: Item, borrowed_on: date | None = None) -> Loan:
        self._require_member(student)
        checkout_date = borrowed_on or self._now().date()
        if self._sign_out_log.has_overdue_loans(student, checkout_date):
            raise OverdueLoansError("Return overdue items before borrowing again.")

        policy = self._policies[item.get_category()]
        reservation = self._active_reservation_for(item)
        if item.status is ItemStatus.RESERVED:
            if reservation is None or reservation.student != student:
                raise ItemUnavailableError("This item is reserved by another student.")
        elif item.status is not ItemStatus.AVAILABLE:
            raise ItemUnavailableError("Item is not available for checkout.")

        if policy.requires_reservation(item) and reservation is None:
            raise ReservationRequiredError("Reserve this item before checking it out.")

        loan = Loan(student, item, checkout_date, policy.calculate_due_date(item, checkout_date))
        item._check_out()
        self._sign_out_log._record(loan)
        if reservation is not None:
            reservation._fulfill()
        return loan

    def reserve(self, student: Student, item: Item, reserved_for: date) -> Reservation:
        self._require_member(student)
        today = self._now().date()
        if self._sign_out_log.has_overdue_loans(student, today):
            raise OverdueLoansError("Return overdue items before reserving another.")
        if item.status is not ItemStatus.AVAILABLE:
            raise ItemUnavailableError("Only available items can be reserved.")
        reservation = Reservation(student, item, reserved_for, self._now())
        item._reserve()
        self._reservations.append(reservation)
        return reservation

    def cancel_reservation(self, reservation: Reservation, requester: Student) -> None:
        self._require_member(requester)
        if reservation not in self._reservations:
            raise InvalidStateError("Reservation does not belong to this club.")
        if requester != reservation.student and requester.role.name != "COORDINATOR":
            raise AuthorizationError("Only the reserving student or a coordinator may cancel.")
        reservation._cancel()
        reservation.item._mark_available()

    def expire_reservations(self, today: date) -> int:
        expired = 0
        for reservation in self._reservations:
            if reservation.status is ReservationStatus.ACTIVE and reservation.reserved_for < today:
                reservation._expire()
                reservation.item._mark_available()
                expired += 1
        return expired

    def return_item(self, loan: Loan, condition: ItemCondition, returned_on: date | None = None) -> None:
        if not self._sign_out_log.contains(loan):
            raise InvalidStateError("Loan does not belong to this club.")
        if not isinstance(condition, ItemCondition):
            raise TypeError("condition must be an ItemCondition.")
        actual_return_date = returned_on or self._now().date()
        loan._close(actual_return_date, condition)
        loan.item._set_condition(condition)
        loan.item._mark_available()
        if condition is ItemCondition.DAMAGED:
            loan.item._retire()

    def _require_member(self, student: Student) -> None:
        if student is None or self._members.get(student.student_id) is not student:
            raise NotMemberError("Student must be registered with this club.")

    def _active_reservation_for(self, item: Item) -> Reservation | None:
        return next((reservation for reservation in self._reservations
                     if reservation.item == item and reservation.status is ReservationStatus.ACTIVE), None)
