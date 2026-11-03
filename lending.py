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
