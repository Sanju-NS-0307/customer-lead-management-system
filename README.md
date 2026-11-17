# Customer and Lead Management System

## About the Project

A small Python and Streamlit application for organizing customer and lead records. It is designed as a practical project for learning Python classes, validation, file handling, and user interfaces.

## Features

- Register and search customers.
- Register leads and update their status.
- Record interaction notes and schedule follow-ups.
- View upcoming and overdue follow-ups.
- View customer totals and lead counts by status.

## Technologies Used

- Python 3.11 or newer
- Streamlit 1.66.1
- JSON-formatted TXT files for local storage
- Python `unittest` for automated tests

Python 3.12.9 is the version verified in the current environment. Python 3.11+ is documented based on the installed Streamlit requirement; other versions have not been verified.

## Project Structure

```text
.
├── customer_lead.py
├── customer_lead_system.py
├── requirements.txt
├── README.md
└── tests/
    ├── test_customer_lead.py
    └── test_customer_lead_system.py
```

The application creates `customers.txt` and `leads.txt` beside `customer_lead.py` when records are saved. These files are local private data and must not be committed to GitHub.

## How to Run

Open PowerShell in the project folder. Create an environment and install the requirements:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the application:

```powershell
.\.venv\Scripts\python.exe -m streamlit run customer_lead_system.py
```

Run the automated tests:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

## Python Concepts Used

- Classes and objects
- Methods and constructors
- Lists and dictionaries
- Input validation and exceptions
- JSON and file handling
- Modules and automated tests

## Data Storage

Customer and lead records are stored locally as JSON in `customers.txt` and `leads.txt`. Keep both files private and outside public repositories. Back them up by copying them to a protected folder outside the project, then compare SHA256 hashes of each source file and its backup before relying on the copy.

