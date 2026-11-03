from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from .enums import DonationStatus, ItemCategory, ItemCondition, NoteType
from .exceptions import InvalidStateError
from .items import Item
from .students import Student
from .validation import require_text


# David's contribution: end-of-semester pass-it-on and student-authored archive stories.
class Donation:
    def __init__(
        self,
        donor: Student,
        item_description: str,
        category: ItemCategory,
        reported_condition: ItemCondition,
        anonymous: bool = False,
        donated_on: date | None = None,
    ) -> None:
        self._id = uuid4()
        self._donor = donor
        self._item_description = require_text(item_description, "item_description")
        self._category = category
        self._reported_condition = reported_condition
        self._anonymous = bool(anonymous)
        self._donated_on = donated_on or date.today()
        self._status = DonationStatus.PENDING
        self._accepted_on: date | None = None

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def item_description(self) -> str:
        return self._item_description

    @property
    def category(self) -> ItemCategory:
        return self._category

    @property
    def reported_condition(self) -> ItemCondition:
        return self._reported_condition

    @property
    def anonymous(self) -> bool:
        return self._anonymous

    @property
    def donated_on(self) -> date:
        return self._donated_on

    @property
    def status(self) -> DonationStatus:
        return self._status

    @property
    def accepted_on(self) -> date | None:
        return self._accepted_on

    def donor_display_name(self, requester: Student, privacy_policy: object) -> str:
        if self._anonymous:
            return "Anonymous"
        return self._donor.display_name(requester, privacy_policy)

    def _accept(self, accepted_on: date) -> None:
        if self._status is not DonationStatus.PENDING:
            raise InvalidStateError("Only a pending donation can be accepted.")
        self._status = DonationStatus.ACCEPTED
        self._accepted_on = accepted_on

    def _reject(self) -> None:
        if self._status is not DonationStatus.PENDING:
            raise InvalidStateError("Only a pending donation can be rejected.")
        self._status = DonationStatus.REJECTED


class LegendEntry:
    def __init__(self, author: Student, item: Item, story: str, anonymous: bool = False,
                 written_on: datetime | None = None) -> None:
        self._id = uuid4()
        self._author = author
        self._item = item
        self._story = require_text(story, "story")
        self._anonymous = bool(anonymous)
        self._written_on = written_on or datetime.now().astimezone()

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def item(self) -> Item:
        return self._item

    @property
    def story(self) -> str:
        return self._story

    @property
    def written_on(self) -> datetime:
        return self._written_on

    @property
    def anonymous(self) -> bool:
        return self._anonymous

    def edit_story(self, story: str, requester: Student) -> None:
        if requester is not self._author:
            raise PermissionError("Only the author may edit this story.")
        self._story = require_text(story, "story")

    def display_author(self, requester: Student, privacy_policy: object) -> str:
        if self._anonymous:
            return "Anonymous"
        return self._author.display_name(requester, privacy_policy)


class Logbook:
    def __init__(self) -> None:
        self._entries: list[LegendEntry] = []

    def _add_entry(self, entry: LegendEntry) -> None:
        self._entries.append(entry)

    def entries(self) -> tuple[LegendEntry, ...]:
        return tuple(self._entries)

    def find_by_item(self, item_id: UUID) -> tuple[LegendEntry, ...]:
        return tuple(entry for entry in self._entries if entry.item.id == item_id)

    def find_by_author(
        self, student_id: str, requester: Student, privacy_policy: object
    ) -> tuple[LegendEntry, ...]:
        is_registered = getattr(privacy_policy, "is_registered")
        can_view_all = getattr(privacy_policy, "can_view_all_loan_details")
        if not is_registered(requester):
            raise PermissionError("Requester must be a registered student.")
        if requester.student_id != student_id and not can_view_all(requester):
            raise PermissionError("Only the author or a coordinator may search by author.")
        return tuple(entry for entry in self._entries if entry._author.student_id == student_id)

    def sorted_by_written_date(self) -> tuple[LegendEntry, ...]:
        return tuple(sorted(self._entries, key=lambda entry: entry.written_on))


class BoardNote:
    def __init__(self, author: Student, text: str, note_type: NoteType,
                 anonymous: bool = False, posted_on: datetime | None = None) -> None:
        self._id = uuid4()
        self._author = author
        self._text = require_text(text, "text")
        self._note_type = note_type
        self._anonymous = bool(anonymous)
        self._posted_on = posted_on or datetime.now().astimezone()
        self._resolved_on: datetime | None = None

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def text(self) -> str:
        return self._text

    @property
    def note_type(self) -> NoteType:
        return self._note_type

    @property
    def posted_on(self) -> datetime:
        return self._posted_on

    @property
    def resolved_on(self) -> datetime | None:
        return self._resolved_on

    @property
    def is_resolved(self) -> bool:
        return self._resolved_on is not None

    def display_author(self, requester: Student, privacy_policy: object) -> str:
        if self._anonymous:
            return "Anonymous"
        return self._author.display_name(requester, privacy_policy)

    def _resolve(self, resolved_on: datetime | None = None) -> None:
        if self.is_resolved:
            raise InvalidStateError("This board note is already resolved.")
        self._resolved_on = resolved_on or datetime.now().astimezone()


class RequestBoard:
    def __init__(self) -> None:
        self._notes: list[BoardNote] = []

    def _post(self, note: BoardNote) -> None:
        self._notes.append(note)

    def get_open_notes(self) -> tuple[BoardNote, ...]:
        return tuple(note for note in self._notes if not note.is_resolved)

    def find_by_type(self, note_type: NoteType) -> tuple[BoardNote, ...]:
        return tuple(note for note in self._notes if note.note_type is note_type)

    def _find(self, note_id: UUID) -> BoardNote | None:
        return next((candidate for candidate in self._notes if candidate.id == note_id), None)

    def _resolve(self, note_id: UUID, resolved_on: datetime | None = None) -> BoardNote:
        note = self._find(note_id)
        if note is None:
            raise KeyError("Board note not found.")
        note._resolve(resolved_on)
        return note

    def notes(self) -> tuple[BoardNote, ...]:
        return tuple(self._notes)
