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
