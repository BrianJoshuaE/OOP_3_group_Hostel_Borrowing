from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta

from .items import Item


# Liron's contribution: interchangeable policies provide polymorphism and the Strategy pattern.
class LoanPolicy(ABC):
    @abstractmethod
    def calculate_due_date(self, item: Item, borrowed_on: date) -> date:
        raise NotImplementedError

    @abstractmethod
    def requires_reservation(self, item: Item) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class AcademicLoanPolicy(LoanPolicy):
    max_loan_days: int = 7

    def __post_init__(self) -> None:
        if self.max_loan_days < 1:
            raise ValueError("max_loan_days must be positive.")

    def calculate_due_date(self, item: Item, borrowed_on: date) -> date:
        return borrowed_on + timedelta(days=self.max_loan_days)

    def requires_reservation(self, item: Item) -> bool:
        return False


@dataclass(frozen=True)
class UtilityLoanPolicy(LoanPolicy):
    max_loan_days: int = 3

    def __post_init__(self) -> None:
        if self.max_loan_days < 1:
            raise ValueError("max_loan_days must be positive.")

    def calculate_due_date(self, item: Item, borrowed_on: date) -> date:
        return borrowed_on + timedelta(days=self.max_loan_days)

    def requires_reservation(self, item: Item) -> bool:
        return False


@dataclass(frozen=True)
class EventLoanPolicy(LoanPolicy):
    max_loan_days: int = 2

    def __post_init__(self) -> None:
        if self.max_loan_days < 1:
            raise ValueError("max_loan_days must be positive.")

    def calculate_due_date(self, item: Item, borrowed_on: date) -> date:
        return borrowed_on + timedelta(days=self.max_loan_days)

    def requires_reservation(self, item: Item) -> bool:
        return True
