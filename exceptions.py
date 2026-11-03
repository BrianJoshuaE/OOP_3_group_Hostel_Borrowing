# Brian's contribution: domain-specific failures shared across the package.
class ArchiveError(Exception):
    """Base exception for expected archive rule violations."""


class ValidationError(ArchiveError):
    pass


class NotMemberError(ArchiveError):
    pass


class ItemUnavailableError(ArchiveError):
    pass


class OverdueLoansError(ArchiveError):
    pass


class ReservationRequiredError(ArchiveError):
    pass


class AuthorizationError(ArchiveError):
    pass


class InvalidStateError(ArchiveError):
    pass


class StorageFullError(ArchiveError):
    pass
