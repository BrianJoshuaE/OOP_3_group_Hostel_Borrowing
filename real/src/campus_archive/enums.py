from enum import Enum, auto


# Kevin's contribution: domain value sets used by people, inventory, and workflows.
class StudentRole(Enum):
    MEMBER = auto()
    COORDINATOR = auto()
    STORYTELLER = auto()


class ItemCategory(Enum):
    ACADEMIC_TECH = auto()
    DORM_UTILITY = auto()
    SOCIAL_LEISURE = auto()


class ItemStatus(Enum):
    AVAILABLE = auto()
    RESERVED = auto()
    ON_LOAN = auto()
    RETIRED = auto()


class ItemCondition(Enum):
    NEW = auto()
    GOOD = auto()
    WORN = auto()
    DAMAGED = auto()


class ReservationStatus(Enum):
    ACTIVE = auto()
    CANCELLED = auto()
    FULFILLED = auto()
    EXPIRED = auto()


class DonationStatus(Enum):
    PENDING = auto()
    ACCEPTED = auto()
    REJECTED = auto()


class NoteType(Enum):
    REQUEST = auto()
    SHOUTOUT = auto()
