from datetime import date

from .club import CampusClub
from .community import LegendEntry
from .enums import ItemCondition, StudentRole
from .items import AcademicTechItem
from .students import Student


def main() -> None:
    club = CampusClub(
        "Campus Survival Archive",
        "We share what we have so nobody has to buy what they only need once.",
    )
    storyteller = Student("S-100", "Alex Rivera", "Maple 214", StudentRole.STORYTELLER)
    borrower = Student("S-101", "Jordan Lee", "Maple 216")
    club.register_student(storyteller)
    club.register_student(borrower)

    calculator = AcademicTechItem(
        "Graphing Calculator", "Graphing calculator with protective case.",
        ItemCondition.GOOD, ["protective case", "USB cable"],
    )
    club.add_item(calculator)
    loan = club.check_out(borrower, calculator)
    print(f"Borrowed {loan.item.name}; due {loan.due_on}.")
    club.return_item(loan, ItemCondition.GOOD)
    club.add_legend_entry(LegendEntry(
        borrower, calculator, "This calculator helped me pass Calculus III."
    ))
    print(f"Returned {calculator.name}; it is now {calculator.status.name.lower()}.")
    print(f"The Logbook of Legends has {len(club.logbook.entries())} entry.")
    print(f"Due-date example: {date.today()} + the category policy.")


if __name__ == "__main__":
    main()
