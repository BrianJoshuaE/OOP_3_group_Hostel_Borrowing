from uuid import uuid4

from .enums import StudentRole
from .validation import require_text


# Kevin's contribution: students are borrowers, donors, authors, and role holders.
class Student:
    def __init__(
        self,
        student_id: str,
        name: str,
        dorm_room: str,
        role: StudentRole = StudentRole.MEMBER,
        show_name_in_logs: bool = True,
    ) -> None:
        self._student_id = require_text(student_id, "student_id")
        self.name = name
        self.dorm_room = dorm_room
        if not isinstance(role, StudentRole):
            raise TypeError("role must be a StudentRole.")
        self._role = role
        self.show_name_in_logs = show_name_in_logs

    @property
    def student_id(self) -> str:
        return self._student_id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = require_text(value, "name")

    @property
    def dorm_room(self) -> str:
        return self._dorm_room

    @dorm_room.setter
    def dorm_room(self, value: str) -> None:
        self._dorm_room = require_text(value, "dorm_room")

    @property
    def role(self) -> StudentRole:
        return self._role

    @property
    def show_name_in_logs(self) -> bool:
        return self._show_name_in_logs

    @show_name_in_logs.setter
    def show_name_in_logs(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("show_name_in_logs must be a bool.")
        self._show_name_in_logs = value

    def display_name(self, requester: Student, privacy_policy: object) -> str:
        if not self._show_name_in_logs:
            return "Campus member"
        can_view = getattr(privacy_policy, "can_view_contact_info")
        return self._name if can_view(requester, self) else "Campus member"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Student) and self._student_id == other._student_id

    def __hash__(self) -> int:
        return hash(self._student_id)

    def __repr__(self) -> str:
        return f"Student(student_id={self._student_id!r}, role={self._role.name})"
