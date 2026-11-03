# Campus Survival Archive: Team Plan

The implementation language is Python. The class diagram is in [campus_survival_archive.puml](campus_survival_archive.puml), and the package source is under `src/campus_archive/`. Shared class names follow that diagram; Python-specific behavior is noted below.

## Member Contributions

<!-- Kevin contribution -->
### Kevin: Inventory and Item Hierarchy

Own `Item`, `AcademicTechItem`, `DormUtilityItem`, `SocialLeisureItem`, and `ItemCategory`, `ItemStatus`, `ItemCondition`.

- Make `Item` abstract, keep fields private, and expose validated getters/mutators.
- Implement subtype-specific data and override category and care-instruction behavior. Use the same public operations across subtypes so callers can use polymorphism.
- Implement item lifecycle transitions: available, reserved, on loan, available after return, or retired when necessary.
- Define stable ID-based equality and hash behavior; add constructors and focused tests for invalid state changes and subtype overrides.
- Coordinate the item constructor and method signatures with Liron before merging.

<!-- Liron contribution -->
### Liron: Lending, Policies, Reservations, and Exceptions

Own `Loan`, `Reservation`, `SignOutLog`, `LoanPolicy` and its strategies, plus lending-related exceptions.

- Implement immutable loan facts (`id`, borrower, item, checkout date, due date, checkout condition); allow the return facts to be recorded once.
- Implement the `AcademicLoanPolicy`, `UtilityLoanPolicy`, and `EventLoanPolicy` strategies with date-based due-date and reservation rules.
- Implement checkout/return validation and reservation lifecycle, including item availability, registered membership, overdue loans, and condition snapshots.
- Add date handling, active/overdue loan queries, retention purge, and sorting/search helpers for loan records.
- Provide overloads where the chosen language supports them. Every overload must delegate to the same validated operation.
- Write tests for normal checkout/return and each rejection path: non-member, unavailable item, overdue borrower, invalid return, and unauthorized log access.

<!-- David contribution -->
### David: Donations and Community Story Features

Own `Donation`, `Logbook`, `LegendEntry`, `RequestBoard`, `BoardNote`, and `NoteType`.

- Implement end-of-semester donations with donor, category, condition, date, and optional anonymity. The club accepts or rejects a donation; acceptance creates and registers an available item through Brian's club workflow.
- Implement the Logbook of Legends, linking each entry to exactly one author and one item, with written date and anonymous display support.
- Implement requests and shout-outs, including posted date, open/resolved state, and resolved date.
- Keep author identity private in public views and validate empty or overlong text.
- Add tests for creating, listing, anonymizing, resolving, and searching stories and notes.

<!-- Warren contribution -->
### Warren: Storage, Catalog, and Discovery

Own `StorageSpace` and `CatalogService`, and collaborate on repository-wide search/sort behavior.

- Implement location/capacity checks and item placement/removal without duplicating inventory ownership.
- Implement catalog search and available-item filtering by category; add sorting by name and date added.
- Keep catalog queries separate from lending decisions. The catalog may show availability but must not expose borrower identity or loan details.
- Add tests for capacity, placement, case-insensitive search, empty results, category filters, and deterministic sorting.
- Prepare a short demo dataset covering a calculator, a dorm utility, and a social item.

<!-- Brian contribution -->
### Brian: Club Facade, Privacy, Integration, and Repository Coordination

As repository creator, own `CampusClub`, `LendingService` orchestration, `PrivacyPolicy`, shared contracts, and final integration.

- Implement `CampusClub` as the public use-case facade: register members, add/find items, check out, return, accept donations, and access community features. Delegate policy and catalog work to their services.
- Enforce role-based access: members can see item availability; coordinators can see protected loan and contact details. Keep student IDs and dorm rooms out of public views.
- Define shared constructors, IDs, exception names, date conventions, and interfaces with the other four members before merge.
- Integrate each module, resolve cross-module tests, and ensure the project builds from a clean checkout. Review pull requests; do not rewrite another member's module without coordinating.
- Add integration tests for donation-to-inventory, checkout-to-log, return-to-item-condition, reservation, and privacy behavior. Maintain the README/run instructions once the language is selected.

## Shared Implementation Rules

- **Encapsulation and access:** fields are private; use public operations that validate changes. Avoid unrestricted setters for IDs, loan dates, status, and roles.
- **Abstraction and responsibilities:** `CampusClub` is the use-case facade; `LendingService`, `CatalogService`, `SignOutLog`, and the community classes own focused work.
- **Inheritance and polymorphism:** abstract `Item` defines shared behavior; the three item types override category and care instructions. `StudentRole.STORYTELLER` is a role, not a `Student` subclass.
- **Strategy pattern:** `LendingService` selects a `LoanPolicy` by item category. Policies implement the same contract and can be substituted without changing checkout orchestration.
- **Duck typing:** this depends on language. In Python, an object that supplies `getCareInstructions()` can be used without inheriting a declared base class. In Java/C#, use a `CareInstructionProvider` interface instead; that is interface polymorphism, not duck typing.
- **Overloading:** Java/C# can declare same-named methods with different parameter lists. Python does not support signature-based overloads at runtime; use an optional parameter or explicit dispatch. Do not let a convenience overload skip validation.
- **Composition and aggregation:** the club owns its log, storage, policy service, catalog, logbook, and board; students and inventory items can exist independently of a club.
- **Privacy and retention:** apply access checks at query boundaries, anonymize public story views, and purge or anonymize closed loan history after the configured retention period.
- **Identity, collections, and time:** compare entities by stable IDs; use collections for inventory, members, loans, reservations, and posts. Use date-only values for due dates and timestamps for events; inject a clock where tests need deterministic dates.
- **Exceptions and state:** use domain exceptions for invalid checkout and access. Keep legal state transitions explicit and test both allowed and rejected transitions.

## Integration Order

1. Brian maintains the agreed Python package layout, build/run commands, naming conventions, and shared method signatures.
2. Kevin and Liron agree on `Item` constructors, category values, lifecycle methods, and `LoanPolicy` inputs.
3. Each member implements their owned classes and unit tests on separate branches or clearly separated files.
4. Brian integrates the modules; Warren verifies inventory search/sort against the integrated item model; David verifies donation acceptance and story links.
5. The team runs unit and integration tests together and demonstrates: donate an item, find it, check it out, return it in a changed condition, and record a story.

## Definition of Done

- The project builds and the demo workflow succeeds.
- Every public operation validates its inputs and reports invalid operations with a clear exception or result.
- Tests cover item subtypes, policy polymorphism, member/overdue checks, reservations, donation acceptance, privacy, retention, search/sort, and the item lifecycle.
- No public view exposes student ID, dorm room, or borrower-level loan details to an ordinary member.
