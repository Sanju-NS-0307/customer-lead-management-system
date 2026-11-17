# Customer and Lead Management System

## About the project

A small Python and Streamlit project for keeping customer and potential-customer information organized. It demonstrates object-oriented programming, validation, collections, exceptions, and local text-file storage.

## Features

- Add, view, search, edit, segment, and delete customer records.
- Add, search, filter, edit, and delete leads; update lead status.
- Record dated interaction notes for customers and leads.
- Add, update, complete, reopen, and delete follow-up reminders.
- See overdue, due today, upcoming, and completed follow-ups.
- Convert an eligible lead into a customer while keeping the lead and linking both records.
- View customer and lead totals and counts for each lead status.

## Technologies

- Python 3.11 or newer (verified with Python 3.12.9).
- Streamlit 1.66.1.
- Python `csv` module for tab-separated text storage.
- Python `unittest` and Streamlit AppTest for automated tests.

## Project files

```text
customer_lead.py                 # Classes, validation, and local data storage
customer_lead_system.py          # Four-page Streamlit application
customer_lead_data.txt           # Created locally when the first record is saved
requirements.txt                 # Application dependency
tests/test_customer_lead.py      # Backend tests
tests/test_customer_lead_system.py  # Streamlit AppTests
```

## Run the application

Open PowerShell in the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run customer_lead_system.py
```

The application has four pages: Dashboard, Customers, Leads, and Follow-ups & Notes.

## Run the tests

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Tests use temporary folders and synthetic records. They do not use the local application data file.

## Data storage and privacy

The application stores customer and lead records, notes, and follow-ups in `customer_lead_data.txt` beside the Python files. It is a tab-separated text file. Fields are quoted when needed, so descriptions can contain punctuation and tabs safely. The application writes a complete temporary file and atomically replaces the previous file after a successful save. Conversion updates the lead and adds its linked customer in the same file replacement.

This file contains private information. Keep it local, do not commit it to a public repository, and back it up to a protected folder outside the project. To back it up, close the application, copy the file to the protected location, then compare SHA256 hashes of the original and the backup before relying on the copy. Protect access to both copies.

This version uses a new tab-separated format. It does not automatically import JSON records from older `customers.txt` or `leads.txt` files. Keep those original files and a verified backup until you have separately reviewed and completed any needed data migration. The application does not delete or overwrite those legacy files.

## Follow-up workflow

Choose a customer or lead on Follow-ups & Notes, add a due date and description, and save the reminder. The page groups open reminders as overdue, due today, or upcoming. You can edit a reminder, mark it complete, reopen it, or delete it. Completed reminders remain available in their own summary.

## Lead conversion

Convert a lead in the Leads page when its status is New, Contacted, or Interested. The application creates a customer with the lead's contact details, changes the lead status to Converted, and stores matching references in both records. The original lead and its notes and follow-ups remain. Since all records are saved in one text file with one atomic replacement, conversion does not depend on two separate file writes or a recovery journal.

## Python concepts used

The project uses classes and objects, constructors, methods, dictionaries and lists, loops, conditional statements, input validation, exception handling, modules, and file handling with the `csv` module.
