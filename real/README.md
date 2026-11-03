# Campus Survival Archive

A small Python OOP implementation of the student-run sharing club. The archive lets registered students borrow shared campus items, donate items, request reservations, and add memories to the Logbook of Legends.

## Run It

Python 3.11 or newer is required. The project uses only the standard library.

In Windows PowerShell, from the project folder:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m campus_archive
```

Run the tests:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The `PYTHONPATH` command is needed because this project uses a `src/` package layout and intentionally has no external runtime dependencies.

## Project Structure

- `src/campus_archive/items.py`: abstract `Item` and academic/tech, dorm utility, and social/leisure subclasses.
- `src/campus_archive/students.py`: student identity, roles, privacy-aware display, and ID-based equality.
- `src/campus_archive/policies.py`: interchangeable category loan policies.
- `src/campus_archive/lending.py`: loans, reservations, sign-out history, and lending validation.
- `src/campus_archive/community.py`: donations, legend entries, logbook, board notes, and request board.
- `src/campus_archive/storage.py`: physical storage capacity and placement.
- `src/campus_archive/catalog.py`: item discovery, filtering, sorting, and structural duck typing.
- `src/campus_archive/privacy.py`: access-control and loan-retention policy.
- `src/campus_archive/club.py`: `CampusClub` facade and workflow orchestration.
- `tests/test_archive.py`: standard-library `unittest` coverage.
- `campus_survival_archive.puml`: class diagram.
- `TEAM_PLAN.md`: contribution boundaries and integration checklist.

## OOP Concepts in the Code

- **Classes, objects, constructors:** `Student`, `Item`, `Loan`, `Donation`, `CampusClub`, and related objects.
- **Encapsulation and access:** state is stored in underscore-prefixed fields; properties expose controlled access, while workflow state changes use internal methods.
- **Abstraction and inheritance:** `Item` is abstract; each concrete item subtype supplies its category and care instructions.
- **Overriding and polymorphism:** item subclasses override abstract behavior; `LoanPolicy` implementations provide different rules behind a common interface.
- **Composition and aggregation:** the club owns its logbook, request board, storage, policy services, and catalog; members and items remain distinct objects.
- **Duck typing:** `care_instructions_for` accepts any object with `get_care_instructions()`. `CareInstructionProvider` is a `Protocol` for static checking; objects need not inherit from it.
- **Method overloading in Python:** Python has no Java-style runtime overload by signature. `CampusClub.check_out` uses `typing.overload` declarations for type checkers and one implementation with an optional date at runtime.
- **Enums and collections:** roles, categories, conditions, and statuses are enums; the club manages typed lists and dictionaries.
- **Validation, exceptions, and lifecycle:** invalid member, availability, overdue, reservation, return, and capacity cases raise domain exceptions; legal status transitions are centralized.
- **Privacy and identity:** students compare by ID for domain identity, while authorization requires the registered object instance. Loan details and student contact data are role-restricted.
- **Dates, searching, and sorting:** checkout, due, return, donation, note, and story timestamps are recorded; the catalog and logs support search and sorting.
- **Static data:** `CampusClub.club_count()` demonstrates class-level data.
- **Single Responsibility Principle:** lending, catalog, privacy, storage, and community workflows have separate classes; the club facade coordinates them.

## Team Ownership

- **Kevin:** enums, students, abstract item, and concrete item types.
- **Liron:** loan policies, loans, reservations, sign-out log, and lending service.
- **David:** donations, legend entries, logbook, board notes, and request board.
- **Warren:** storage, catalog, search/sorting, and duck-typing example.
- **Brian:** club facade, privacy, exceptions, package integration, and end-to-end tests.

Each module has a contribution comment naming its owner. Coordinate shared API changes before editing another member's module.
