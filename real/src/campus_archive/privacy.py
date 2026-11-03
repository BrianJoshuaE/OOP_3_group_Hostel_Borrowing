from datetime import date, timedelta

from .enums import StudentRole
from .lending import Loan
from .students import Student


# Brian's contribution: centralized access decisions and record-retention policy.
class PrivacyPolicy:
    def __init__(self, members: dict[str, Student], retention_days: int = 180,
                 overdue_coordinator_only: bool = True) -> None:
        if retention_days < 1:
            raise ValueError("retention_days must be positive.")
        self._members = members
        self._retention_days = retention_days
        self._overdue_coordinator_only = overdue_coordinator_only

    @property
    def retention_days(self) -> int:
        return self._retention_days

    def can_view_loan_details(self, requester: Student, loan: Loan) -> bool:
        if not self.is_registered(requester):
            return False
        return requester is loan.borrower or requester.role is StudentRole.COORDINATOR

    def can_view_contact_info(self, requester: Student, subject: Student) -> bool:
        if not self.is_registered(requester):
            return False
        if requester is subject:
            return True
        return (self.is_registered(subject)
                and requester.role is StudentRole.COORDINATOR)

    def can_view_overdue_details(self, requester: Student) -> bool:
        return (self.is_registered(requester)
                and (not self._overdue_coordinator_only
                     or requester.role is StudentRole.COORDINATOR))

    def can_view_all_loan_details(self, requester: Student) -> bool:
        return self.is_registered(requester) and requester.role is StudentRole.COORDINATOR

    def is_registered(self, student: Student) -> bool:
        return student is not None and self._members.get(student.student_id) is student

    def is_expired(self, loan: Loan, today: date) -> bool:
        return loan.returned_on is not None and loan.returned_on + timedelta(days=self._retention_days) < today
