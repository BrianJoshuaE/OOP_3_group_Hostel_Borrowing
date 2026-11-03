from datetime import date, datetime, timezone
import unittest

from campus_archive import (
    AcademicTechItem,
    BoardNote,
    CampusClub,
    Donation,
    DormUtilityItem,
    ItemCategory,
    ItemCondition,
    ItemStatus,
    LegendEntry,
    NoteType,
    ReservationRequiredError,
    Student,
    StudentRole,
    SocialLeisureItem,
    NotMemberError,
    OverdueLoansError,
    ItemUnavailableError,
    AuthorizationError,
    StorageFullError,
    care_instructions_for,
)


class ArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = date(2026, 11, 3)
        self.clock_value = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
        self.club = CampusClub(
            "Test Archive", "We share and reuse.", storage_capacity=10,
            now=lambda: self.clock_value,
        )
        self.coordinator = Student("C-1", "Casey Coordinator", "Hall 1", StudentRole.COORDINATOR)
        self.member = Student("M-1", "Morgan Member", "Hall 2")
        self.club.register_student(self.coordinator)
        self.club.register_student(self.member)

    def test_checkout_and_return_track_dates_and_condition(self) -> None:
        calculator = AcademicTechItem("Calculator", "Graphing calculator", accessories=["case"])
        self.club.add_item(calculator)
        loan = self.club.check_out(self.member, calculator, self.today)

        self.assertEqual(loan.due_on, date(2026, 11, 10))
        self.assertEqual(loan.condition_on_checkout, ItemCondition.GOOD)
        self.assertEqual(calculator.status, ItemStatus.ON_LOAN)

        self.club.return_item(loan, ItemCondition.WORN, date(2026, 11, 5))
        self.assertEqual(loan.returned_on, date(2026, 11, 5))
        self.assertEqual(loan.condition_on_return, ItemCondition.WORN)
        self.assertEqual(calculator.condition, ItemCondition.WORN)
        self.assertEqual(calculator.status, ItemStatus.AVAILABLE)

    def test_non_member_cannot_borrow(self) -> None:
        item = AcademicTechItem("Calculator", "Graphing calculator")
        outsider = Student("X-1", "Outside Student", "Hall 3")
        self.club.add_item(item)
        with self.assertRaises(NotMemberError):
            self.club.check_out(outsider, item)

    def test_overdue_borrower_is_blocked(self) -> None:
        first = AcademicTechItem("Calculator", "Graphing calculator")
        second = DormUtilityItem("Toolkit", "Basic tools")
        self.club.add_item(first)
        self.club.add_item(second)
        self.club.check_out(self.member, first, date(2026, 10, 1))
        with self.assertRaises(OverdueLoansError):
            self.club.check_out(self.member, second, self.today)

    def test_unavailable_item_cannot_be_borrowed_twice(self) -> None:
        item = AcademicTechItem("Calculator", "Graphing calculator")
        self.club.add_item(item)
        self.club.check_out(self.member, item, self.today)
        with self.assertRaises(ItemUnavailableError):
            self.club.check_out(self.coordinator, item, self.today)

    def test_social_item_requires_reservation(self) -> None:
        projector = SocialLeisureItem("Projector", "Movie-night projector")
        self.club.add_item(projector)
        with self.assertRaises(ReservationRequiredError):
            self.club.check_out(self.member, projector, self.today)
        reservation = self.club.reserve(self.member, projector, date(2026, 11, 5))
        loan = self.club.check_out(self.member, projector, self.today)
        self.assertEqual(reservation.status.name, "FULFILLED")
        self.club.return_item(loan, ItemCondition.GOOD, date(2026, 11, 4))

    def test_reservation_can_be_cancelled_or_expired(self) -> None:
        cancelled_item = SocialLeisureItem("Speaker", "Party speaker")
        expired_item = SocialLeisureItem("Projector", "Movie-night projector")
        self.club.add_item(cancelled_item)
        self.club.add_item(expired_item)

        cancelled = self.club.reserve(self.member, cancelled_item, date(2026, 11, 5))
        self.club.cancel_reservation(cancelled, self.member)
        self.assertEqual(cancelled_item.status, ItemStatus.AVAILABLE)

        expired = self.club.reserve(self.member, expired_item, date(2026, 11, 4))
        count = self.club.expire_reservations(date(2026, 11, 5))
        self.assertEqual(count, 1)
        self.assertEqual(expired.status.name, "EXPIRED")
        self.assertEqual(expired_item.status, ItemStatus.AVAILABLE)

    def test_student_cannot_change_role_through_property(self) -> None:
        with self.assertRaises(AttributeError):
            self.member.role = StudentRole.COORDINATOR

    def test_invalid_return_does_not_close_loan(self) -> None:
        item = AcademicTechItem("Calculator", "Graphing calculator")
        self.club.add_item(item)
        loan = self.club.check_out(self.member, item, self.today)
        with self.assertRaises(TypeError):
            self.club.return_item(loan, "damaged")
        self.assertFalse(loan.is_returned)
        self.assertEqual(item.status, ItemStatus.ON_LOAN)

    def test_anonymous_records_do_not_publish_author_or_donor(self) -> None:
        item = AcademicTechItem("Calculator", "Graphing calculator")
        self.club.add_item(item)
        entry = LegendEntry(self.member, item, "Aced the exam.", anonymous=True)
        note = BoardNote(self.member, "Need a projector", NoteType.REQUEST, anonymous=True)
        donation = Donation(self.member, "Lamp", ItemCategory.DORM_UTILITY,
                            ItemCondition.GOOD, anonymous=True)
        self.assertFalse(hasattr(entry, "author"))
        self.assertFalse(hasattr(note, "author"))
        self.assertFalse(hasattr(donation, "donor"))
        self.assertEqual(self.club.member_count, 2)

    def test_archive_managers_do_not_expose_unchecked_write_methods(self) -> None:
        self.assertFalse(hasattr(self.club.sign_out_log, "record"))
        self.assertFalse(hasattr(self.club.sign_out_log, "purge_expired"))
        self.assertFalse(hasattr(self.club.logbook, "add_entry"))
        self.assertFalse(hasattr(self.club.request_board, "post"))
        self.assertFalse(hasattr(self.club.request_board, "resolve"))
        self.assertFalse(hasattr(self.club.storage, "store"))

    def test_damaged_return_retires_item(self) -> None:
        speaker = SocialLeisureItem("Speaker", "Party speaker")
        self.club.add_item(speaker)
        reservation = self.club.reserve(self.member, speaker, date(2026, 11, 4))
        loan = self.club.check_out(self.member, speaker, self.today)
        self.assertEqual(reservation.status.name, "FULFILLED")
        self.club.return_item(loan, ItemCondition.DAMAGED, date(2026, 11, 4))
        self.assertEqual(speaker.status, ItemStatus.RETIRED)

    def test_donation_creates_available_item(self) -> None:
        donation = Donation(
            self.member, "Portable speaker", ItemCategory.SOCIAL_LEISURE,
            ItemCondition.GOOD, anonymous=True, donated_on=self.today,
        )
        item = self.club.accept_donation(donation)
        self.assertEqual(item.status, ItemStatus.AVAILABLE)
        self.assertEqual(donation.status.name, "ACCEPTED")
        self.assertIn(donation, self.club.donations)

    def test_privacy_hides_loan_details_and_personal_fields(self) -> None:
        item = AcademicTechItem("Lamp", "Desk lamp")
        self.club.add_item(item)
        self.club.check_out(self.member, item, self.today)
        self.assertEqual(len(self.club.sign_out_log.find_active_loans(self.member)), 1)
        self.assertEqual(self.club.sign_out_log.find_active_loans(self.coordinator)[0].borrower, self.member)
        with self.assertRaises(AuthorizationError):
            self.club.sign_out_log.find_overdue(self.member, self.today)
        forged_member = Student(self.member.student_id, "Imposter", "Hall 99")
        with self.assertRaises(AuthorizationError):
            self.club.sign_out_log.find_active_loans(forged_member)
        with self.assertRaises(NotMemberError):
            self.club.check_out(forged_member, item, self.today)
        forged_coordinator = Student("C-1", "Imposter Coordinator", "Hall 99", StudentRole.COORDINATOR)
        with self.assertRaises(AuthorizationError):
            self.club.sign_out_log.find_overdue(forged_coordinator, self.today)
        self.assertEqual(self.member.display_name(self.coordinator, self.club.privacy_policy), "Morgan Member")
        self.assertEqual(self.member.display_name(Student("X", "Visitor", "Hall"), self.club.privacy_policy), "Campus member")

    def test_legend_and_board_note_workflows(self) -> None:
        item = AcademicTechItem("Calculator", "Graphing calculator")
        self.club.add_item(item)
        entry = LegendEntry(self.member, item, "Aced the exam.", anonymous=True)
        self.club.add_legend_entry(entry)
        self.assertEqual(entry.display_author(self.coordinator, self.club.privacy_policy), "Anonymous")
        self.assertEqual(len(self.club.logbook.find_by_item(item.id)), 1)
        impostor = Student(self.member.student_id, "Imposter", "Hall 99")
        with self.assertRaises(PermissionError):
            entry.edit_story("Changed the story.", impostor)

        note = BoardNote(self.member, "Need a projector Friday", NoteType.REQUEST)
        self.club.post_board_note(note)
        self.assertEqual(len(self.club.request_board.get_open_notes()), 1)
        self.club.resolve_board_note(note.id, self.member)
        self.assertTrue(note.is_resolved)

    def test_only_author_or_coordinator_can_resolve_a_note(self) -> None:
        note = BoardNote(self.member, "Need a projector", NoteType.REQUEST)
        self.club.post_board_note(note)
        impostor = Student(self.member.student_id, "Imposter", "Hall 99")
        with self.assertRaises(NotMemberError):
            self.club.resolve_board_note(note.id, impostor)
        other_member = Student("M-2", "Other", "Hall 3")
        self.club.register_student(other_member)
        with self.assertRaises(AuthorizationError):
            self.club.resolve_board_note(note.id, other_member)
        self.club.resolve_board_note(note.id, self.coordinator)
        self.assertTrue(note.is_resolved)

    def test_only_coordinator_can_purge_records(self) -> None:
        with self.assertRaises(AuthorizationError):
            self.club.purge_expired_loans(self.member)

    def test_search_filter_sort_and_duck_typing(self) -> None:
        calculator = AcademicTechItem("Graphing Calculator", "For exam week", accessories=["case"])
        toolkit = DormUtilityItem("Toolkit", "Basic dorm repair kit", safety_instructions="Use tools carefully.")
        self.club.add_item(calculator)
        self.club.add_item(toolkit)
        self.assertEqual(self.club.search_items("CALCULATOR"), (calculator,))
        self.assertEqual(self.club.find_available_items(ItemCategory.DORM_UTILITY), (toolkit,))

        class BorrowedObjectWithSameMethod:
            def get_care_instructions(self) -> str:
                return "No inheritance required."

        self.assertEqual(care_instructions_for(calculator), "Return with: case")
        self.assertEqual(care_instructions_for(BorrowedObjectWithSameMethod()), "No inheritance required.")

    def test_storage_capacity(self) -> None:
        small_club = CampusClub("Small", "Small shelf.", storage_capacity=1)
        small_club.add_item(AcademicTechItem("First", "First item"))
        with self.assertRaises(StorageFullError):
            small_club.add_item(AcademicTechItem("Second", "Second item"))

    def test_overloads_share_one_validated_implementation(self) -> None:
        item = AcademicTechItem("Calculator", "Graphing calculator")
        self.club.add_item(item)
        loan = self.club.check_out(self.member, item)
        self.club.return_item(loan)
        self.assertIsNotNone(loan.returned_on)


if __name__ == "__main__":
    unittest.main()
