from datetime import date
from typing import TypeVar

from .exceptions import ValidationError

T = TypeVar("T")


def require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} cannot be blank.")
    return value.strip()


def require_instance(value: T, expected_type: type, field_name: str) -> T:
    if not isinstance(value, expected_type):
        raise ValidationError(f"{field_name} must be a {expected_type.__name__}.")
    return value


def require_date(value: date, field_name: str) -> date:
    if not isinstance(value, date):
        raise ValidationError(f"{field_name} must be a date.")
    return value
