# OOP 3 Group Hostel Borrowing

A Python object-oriented program for managing a shared borrowing club in a
hostel. It keeps track of students, shared items, loans, due dates, returns,
and item condition.

## The Story

Greenview Hostel is home to around 120 students. When someone needs an iron, a
toolkit, or a calculator for a short time, buying one may not make sense—and
borrowing from a neighbor can be hard to keep track of.

To help, the hostel warden and students started the **Hostel Borrowing Club**.
A club keeper looks after shared items in a storeroom and records each
checkout and return, including who borrowed the item, their room, the times,
and the item's condition. Students can check what is available, while the
club keeps a history to help prevent items from going missing.

## What the program can do

- Register students with an ID, name, block, room number, and phone number.
- Add items from categories such as Electrical, Tools, Kitchen, Academic, and
  Sports.
- Check item availability and condition.
- Borrow and return items, recording who borrowed them, when they were taken,
  their due date, and their condition at checkout and return.
- Report overdue loans and borrowing histories.
- Enforce a borrowing limit, block students with overdue loans, and allow one
  extension when nobody is waiting for the item.
- Manage an item's waiting list, repairs, and retirement.
- Show most-borrowed and most-often-damaged item reports.

Loan periods depend on the item category: Electrical (2 days), Tools (3 days),
Kitchen (1 day), Academic (7 days), and Sports (2 days).

## Requirements

- Python 3.8 or newer
- No third-party packages

## Run the program

Open this folder in VS Code and run `hostel_borrowing_club.py`, or open a
terminal in this folder and use:

```powershell
python hostel_borrowing_club.py
```

Choose the guided demo or interactive menu when prompted. You can also start
one directly:

```powershell
python hostel_borrowing_club.py --demo
python hostel_borrowing_club.py --menu
```

The interactive menu asks the club keeper to sign in. The sample program uses
the demo PIN `1234`.

## Sample data

The program starts with example students and these six items:

| Item ID | Item | Category |
|---|---|---|
| ITM-001 | Steam Iron | Electrical |
| ITM-002 | Extension Cord | Electrical |
| ITM-003 | Toolkit | Tools |
| ITM-004 | Hot Pot | Kitchen |
| ITM-005 | Scientific Calculator | Academic |
| ITM-006 | Football | Sports |

Item and loan records are kept in memory while the program runs. They are not
saved to a file or database, so changes are lost when the program exits.

## Object-oriented concepts demonstrated

The code demonstrates classes and objects, constructors, encapsulation with
properties, abstraction, inheritance, method overriding, polymorphism, duck
typing, composition, aggregation, enums, exceptions, collections, and a loan
policy strategy. Assignment comments in the Python file mark each group
member's contribution.

## Group members

- Brian Joshua Elimu
- Warren Joshua Obitre
- David Anthony Loku 
- Ninsiima Kevin
- Akankwasa Kevin

## Note

This is an educational example. The sample PIN and in-memory storage are
intended for demonstration, not for securing or operating a real borrowing
service.
