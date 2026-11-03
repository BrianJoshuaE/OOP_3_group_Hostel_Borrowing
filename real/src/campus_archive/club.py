from __future__ import annotations

from datetime import date, datetime
from typing import Callable, ClassVar, overload
from uuid import UUID, uuid4

from .catalog import CatalogService
from .community import BoardNote, Donation, LegendEntry, Logbook, RequestBoard
from .enums import DonationStatus, ItemCategory, ItemCondition, ItemStatus
from .exceptions import AuthorizationError, ItemUnavailableError, NotMemberError
from .items import AcademicTechItem, DormUtilityItem, Item, SocialLeisureItem
from .lending import LendingService, Loan, Reservation, SignOutLog
from .privacy import PrivacyPolicy
from .storage import StorageSpace
from .students import Student


# Brian's contribution: aggregate root/facade, validation, composition, and team integration.
class CampusClub:
    _club_count: ClassVar[int] = 0

    def __init__(
        self,
        name: str,
        origin_story: str,
        location: str = "Student hub shelf",
        storage_capacity: int = 100,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not name.strip() or not origin_story.strip():
            raise ValueError("Club name and origin story cannot be blank.")
        self._id: UUID = uuid4()
        self._name = name.strip()
        self._origin_story = origin_story.strip()
        self._now = now or (lambda: datetime.now().astimezone())
        self._members: dict[str, Student] = {}
        self._inventory: list[Item] = []
        self._donations: list[Donation] = []
        self._storage = StorageSpace(location, storage_capacity)
        self._privacy_policy = PrivacyPolicy(self._members)
        self._sign_out_log = SignOutLog(self._privacy_policy)
        self._logbook = Logbook()
        self._request_board = RequestBoard()
        self._catalog = CatalogService(self._inventory)
        self._lending = LendingService(self._members, self._sign_out_log, self._now)
        type(self)._club_count += 1

    @classmethod
    def club_count(cls) -> int:
        return cls._club_count

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def origin_story(self) -> str:
        return self._origin_story

    @property
    def storage(self) -> StorageSpace:
        return self._storage

    @property
    def privacy_policy(self) -> PrivacyPolicy:
        return self._privacy_policy

    @property
    def sign_out_log(self) -> SignOutLog:
        return self._sign_out_log

    @property
    def logbook(self) -> Logbook:
        return self._logbook

    @property
    def request_board(self) -> RequestBoard:
        return self._request_board

    @property
    def member_count(self) -> int:
        return len(self._members)

    @property
    def inventory(self) -> tuple[Item, ...]:
        return tuple(self._inventory)

    @property
    def donations(self) -> tuple[Donation, ...]:
        return tuple(self._donations)

    def register_student(self, student: Student) -> None:
        existing = self._members.get(student.student_id)
        if existing is not None and existing is not student:
            raise ValueError("A different student already uses this student ID.")
        self._members[student.student_id] = student

    def is_member(self, student: Student) -> bool:
        return student is not None and self._members.get(student.student_id) is student

    def add_item(self, item: Item) -> None:
        if item in self._inventory:
            raise ValueError("Item is already in this club's inventory.")
        self._storage._store(item)
        self._inventory.append(item)

    @overload
    def check_out(self, student: Student, item: Item) -> Loan: ...

    @overload
    def check_out(self, student: Student, item: Item, borrowed_on: date) -> Loan: ...

    def check_out(self, student: Student, item: Item, borrowed_on: date | None = None) -> Loan:
        """Overload-style API: today's date by default, or an explicit checkout date."""
        if item not in self._inventory:
            raise ItemUnavailableError("Item is not in this club's inventory.")
        return self._lending.check_out(student, item, borrowed_on or self._now().date())

    def return_item(
        self,
        loan: Loan,
        condition: ItemCondition | None = None,
        returned_on: date | None = None,
    ) -> None:
        """One validated implementation supports default and explicit return details."""
        actual_condition = condition if condition is not None else loan.item.condition
        self._lending.return_item(loan, actual_condition, returned_on or self._now().date())

    def reserve(self, student: Student, item: Item, reserved_for: date) -> Reservation:
        if item not in self._inventory:
            raise ItemUnavailableError("Item is not in this club's inventory.")
        return self._lending.reserve(student, item, reserved_for)

    def cancel_reservation(self, reservation: Reservation, requester: Student) -> None:
        self._lending.cancel_reservation(reservation, requester)

    def expire_reservations(self, today: date | None = None) -> int:
        return self._lending.expire_reservations(today or self._now().date())

    def accept_donation(self, donation: Donation) -> Item:
        if not self.is_member(donation._donor):
            raise NotMemberError("Donor must be a registered student.")
        if donation.status is not DonationStatus.PENDING:
            raise ValueError("Only pending donations can be accepted.")

        description = donation.item_description
        match donation.category:
            case ItemCategory.ACADEMIC_TECH:
                item = AcademicTechItem(description, description, donation.reported_condition)
            case ItemCategory.DORM_UTILITY:
                item = DormUtilityItem(description, description, donation.reported_condition)
            case ItemCategory.SOCIAL_LEISURE:
                item = SocialLeisureItem(description, description, donation.reported_condition)
            case _:
                raise ValueError("Unsupported donation category.")

        # Add first so a full shelf cannot leave a donation marked accepted without an item.
        self.add_item(item)
        donation._accept(self._now().date())
        self._donations.append(donation)
        return item

    def reject_donation(self, donation: Donation, requester: Student) -> None:
        self._require_coordinator(requester)
        if donation.status is not DonationStatus.PENDING:
            raise ValueError("Only pending donations can be rejected.")
        donation._reject()
        self._donations.append(donation)

    def add_legend_entry(self, entry: LegendEntry) -> None:
        self._require_member(entry._author)
        if entry.item not in self._inventory:
            raise ItemUnavailableError("Story item is not in this club's inventory.")
        self._logbook._add_entry(entry)

    def post_board_note(self, note: BoardNote) -> None:
        self._require_member(note._author)
        self._request_board._post(note)

    def resolve_board_note(
        self, note_id: UUID, requester: Student, resolved_on: datetime | None = None
    ) -> None:
        self._require_member(requester)
        note = self._request_board._find(note_id)
        if note is None:
            raise KeyError("Board note not found.")
        if requester is not note._author and requester.role.name != "COORDINATOR":
            raise AuthorizationError("Only the note author or a coordinator may resolve it.")
        self._request_board._resolve(note_id, resolved_on)

    def find_available_items(self, category: ItemCategory | None = None) -> tuple[Item, ...]:
        return self._catalog.find_available(category)

    def search_items(self, query: str) -> tuple[Item, ...]:
        return self._catalog.search(query)

    def purge_expired_loans(self, requester: Student, today: date | None = None) -> int:
        self._require_coordinator(requester)
        actual_today = today or self._now().date()
        return self._sign_out_log._purge_expired(actual_today, self._privacy_policy.retention_days)

    def _require_member(self, student: Student) -> None:
        if not self.is_member(student):
            raise NotMemberError("Student must be registered with this club.")

    def _require_coordinator(self, student: Student) -> None:
        self._require_member(student)
        if student.role.name != "COORDINATOR":
            raise AuthorizationError("Coordinator role is required for this action.")
