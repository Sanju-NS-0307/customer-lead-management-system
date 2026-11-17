
"""
Customer and Lead Management System
Core Python backend with TXT file persistence.
"""

import json
import os
from pathlib import Path
import tempfile
from datetime import date, datetime, timedelta


class Customer:
    """Stores information about a registered customer."""

    def __init__(
        self,
        customer_id,
        name,
        phone,
        email,
        category="Regular",
        source_lead_id=None,
    ):
        self.customer_id = customer_id
        self.name = name.strip()
        self.phone = phone.strip()
        self.email = email.strip()
        self.category = category
        self.source_lead_id = source_lead_id

    def display_details(self):
        return (
            f"Customer ID: {self.customer_id}\n"
            f"Name: {self.name}\n"
            f"Phone: {self.phone}\n"
            f"Email: {self.email}\n"
            f"Category: {self.category}"
        )


class Lead:
    """Stores information about a potential customer."""

    VALID_INTERACTION_TYPES = ["Call", "Email", "Meeting", "Other"]

    VALID_STATUSES = [
        "New",
        "Contacted",
        "Interested",
        "Converted",
        "Lost",
    ]

    def __init__(
        self,
        lead_id,
        name,
        phone,
        email,
        source,
        status="New",
        notes=None,
        follow_up_date=None,
        converted_customer_id=None,
    ):
        if status not in self.VALID_STATUSES:
            raise ValueError("Invalid lead status.")

        self.lead_id = lead_id
        self.name = name.strip()
        self.phone = phone.strip()
        self.email = email.strip()
        self.source = source.strip()
        self.status = status
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.notes = notes if notes is not None else []
        self.follow_up_date = self.normalize_follow_up_date(follow_up_date)
        self.converted_customer_id = converted_customer_id

    @staticmethod
    def normalize_follow_up_date(value):
        """Return a strict ISO date string or None for no scheduled date."""
        if value is None:
            return None

        if isinstance(value, datetime):
            raise ValueError("Follow-up date must use YYYY-MM-DD.")

        if isinstance(value, date):
            return value.isoformat()

        if not isinstance(value, str):
            raise ValueError("Follow-up date must use YYYY-MM-DD.")

        try:
            parsed_date = date.fromisoformat(value)
        except ValueError:
            raise ValueError("Follow-up date must use YYYY-MM-DD.") from None

        if parsed_date.isoformat() != value:
            raise ValueError("Follow-up date must use YYYY-MM-DD.")

        return value

    def set_follow_up_date(self, value):
        """Set or clear the lead's single scheduled follow-up date."""
        self.follow_up_date = self.normalize_follow_up_date(value)

    def add_interaction_note(self, interaction_type, description):
        """Add a dated interaction note after validating its details."""
        interaction_type = interaction_type.strip()
        description = description.strip()

        if interaction_type not in self.VALID_INTERACTION_TYPES:
            raise ValueError(
                "Invalid interaction type. Choose from: "
                f"{', '.join(self.VALID_INTERACTION_TYPES)}"
            )

        if not description:
            raise ValueError("Interaction description cannot be empty.")

        note = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "interaction_type": interaction_type,
            "description": description,
        }
        self.notes.append(note)
        return note

    def update_status(self, new_status):
        """Update the lead's status after validating it."""
        if new_status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid status. Choose from: {', '.join(self.VALID_STATUSES)}"
            )
        if new_status == "Converted":
            raise ValueError("Converted is a historical status and cannot be set directly.")
        if self.converted_customer_id is not None and new_status != "Converted":
            raise ValueError("A converted lead cannot change to another status.")

        self.status = new_status

    def display_details(self):
        return (
            f"Lead ID: {self.lead_id}\n"
            f"Name: {self.name}\n"
            f"Phone: {self.phone}\n"
            f"Email: {self.email}\n"
            f"Source: {self.source}\n"
            f"Status: {self.status}\n"
            f"Created At: {self.created_at}"
        )


class DataLoadError(ValueError):
    """Raised when customer or lead data cannot be loaded safely."""


class DataSaveError(OSError):
    """Raised when customer or lead data cannot be saved safely."""


class CustomerLeadManager:
    """Manages customers, leads, and TXT file storage."""

    def __init__(self, data_dir=None):
        self.customers = {}
        self.leads = {}

        directory = (
            Path(data_dir)
            if data_dir is not None
            else Path(__file__).resolve().parent
        )
        self.customers_file = str(directory / "customers.txt")
        self.leads_file = str(directory / "leads.txt")

        self.load_data()

    @staticmethod
    def validate_contact(name, phone, email):
        """Validate customer or lead contact information."""
        if not name.strip():
            raise ValueError("Name cannot be empty.")

        phone = phone.strip()
        if not phone.isdigit() or len(phone) != 10:
            raise ValueError(
                "Phone number must contain exactly 10 digits."
            )

        email = email.strip()
        if (
            not email
            or "@" not in email
            or "." not in email.rsplit("@", 1)[-1]
        ):
            raise ValueError("Please enter a valid email address.")

    @staticmethod
    def next_id(prefix, records):
        """Generate the next ID without reusing existing IDs."""
        highest_number = 0

        for record_id in records:
            suffix = record_id.removeprefix(prefix)

            if suffix.isdigit():
                highest_number = max(highest_number, int(suffix))

        return f"{prefix}{highest_number + 1:03d}"

    def load_data(self):
        """Load both files completely before replacing the current state."""
        customers = self._load_customers()
        leads = self._load_leads()
        self._validate_customer_lead_links(customers, leads)

        self.customers = customers
        self.leads = leads

    def _read_records(self, file_path, record_type):
        """Read one JSON array, treating missing and empty files as empty."""
        if not os.path.exists(file_path):
            return []

        filename = Path(file_path).name
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                contents = file.read()
        except (OSError, UnicodeError):
            raise DataLoadError(
                f"Could not read {record_type} data file '{filename}'."
            ) from None

        if not contents.strip():
            return []

        try:
            records = json.loads(contents)
        except json.JSONDecodeError:
            raise DataLoadError(
                f"Malformed JSON in {record_type} data file '{filename}'."
            ) from None

        if not isinstance(records, list):
            raise DataLoadError(
                f"Invalid {record_type} data in '{filename}': expected a JSON array."
            )

        return records

    @staticmethod
    def _validate_string_fields(record, fields, record_type, filename, index):
        for field in fields:
            if field not in record:
                raise DataLoadError(
                    f"Invalid {record_type} record {index} in '{filename}': "
                    f"missing required field '{field}'."
                )
            if not isinstance(record[field], str):
                raise DataLoadError(
                    f"Invalid {record_type} record {index} in '{filename}': "
                    f"field '{field}' must be text."
                )

    def _load_customers(self):
        filename = Path(self.customers_file).name
        records = self._read_records(self.customers_file, "customer")
        return self._customers_from_records(records, filename)

    def _customers_from_records(self, records, filename):
        customers = {}
        required_fields = ("customer_id", "name", "phone", "email")
        allowed_fields = set(required_fields) | {"category", "source_lead_id"}

        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                raise DataLoadError(
                    f"Invalid customer record {index} in '{filename}': "
                    "expected an object."
                )

            self._validate_string_fields(
                record, required_fields, "customer", filename, index
            )
            if "category" in record and not isinstance(record["category"], str):
                raise DataLoadError(
                    f"Invalid customer record {index} in '{filename}': "
                    "field 'category' must be text."
                )
            source_lead_id = record.get("source_lead_id")
            if source_lead_id is not None and (
                not isinstance(source_lead_id, str) or not source_lead_id.strip()
            ):
                raise DataLoadError(
                    f"Invalid customer record {index} in '{filename}': "
                    "field 'source_lead_id' must be a non-empty ID or null."
                )
            if set(record) - allowed_fields:
                raise DataLoadError(
                    f"Invalid customer record {index} in '{filename}': "
                    "unexpected fields."
                )

            customer_id = record["customer_id"]
            if not customer_id.strip() or customer_id in customers:
                raise DataLoadError(
                    f"Invalid customer record {index} in '{filename}': "
                    "empty or duplicate ID."
                )

            customers[customer_id] = Customer(**record)

        return customers

    def _load_leads(self):
        filename = Path(self.leads_file).name
        records = self._read_records(self.leads_file, "lead")
        return self._leads_from_records(records, filename)

    def _leads_from_records(self, records, filename):
        leads = {}
        required_fields = (
            "lead_id",
            "name",
            "phone",
            "email",
            "source",
            "status",
            "created_at",
        )

        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                raise DataLoadError(
                    f"Invalid lead record {index} in '{filename}': "
                    "expected an object."
                )

            self._validate_string_fields(
                record, required_fields, "lead", filename, index
            )

            notes = record.get("notes", [])
            if notes is None:
                notes = []
            if not isinstance(notes, list):
                raise DataLoadError(
                    f"Invalid lead record {index} in '{filename}': "
                    "field 'notes' must be an array."
                )
            for note_index, note in enumerate(notes, start=1):
                if not isinstance(note, dict) or any(
                    not isinstance(note.get(field), str)
                    for field in ("date", "interaction_type", "description")
                ):
                    raise DataLoadError(
                        f"Invalid note {note_index} in lead record {index} "
                        f"in '{filename}'."
                    )

            lead_id = record["lead_id"]
            if not lead_id.strip() or lead_id in leads:
                raise DataLoadError(
                    f"Invalid lead record {index} in '{filename}': "
                    "empty or duplicate ID."
                )

            converted_customer_id = record.get("converted_customer_id")
            if converted_customer_id is not None and (
                not isinstance(converted_customer_id, str)
                or not converted_customer_id.strip()
            ):
                raise DataLoadError(
                    f"Invalid lead record {index} in '{filename}': "
                    "field 'converted_customer_id' must be a non-empty ID or null."
                )

            try:
                follow_up_date = Lead.normalize_follow_up_date(
                    record.get("follow_up_date")
                )
            except ValueError:
                raise DataLoadError(
                    f"Invalid follow-up date in lead record {index} "
                    f"in '{filename}'."
                ) from None

            try:
                lead = Lead(
                    record["lead_id"],
                    record["name"],
                    record["phone"],
                    record["email"],
                    record["source"],
                    record["status"],
                    notes,
                    follow_up_date,
                    converted_customer_id,
                )
            except ValueError:
                raise DataLoadError(
                    f"Invalid status in lead record {index} in '{filename}'."
                ) from None
            lead.created_at = record["created_at"]
            leads[lead_id] = lead

        return leads

    @staticmethod
    def _validate_customer_lead_links(customers, leads):
        """Validate optional links stored in older converted records."""
        linked_lead_ids = set()
        for customer in customers.values():
            lead_id = customer.source_lead_id
            if lead_id is None:
                continue
            if lead_id in linked_lead_ids:
                raise DataLoadError(
                    "Multiple customers reference the same source lead."
                )
            linked_lead_ids.add(lead_id)
            lead = leads.get(lead_id)
            if (
                lead is None
                or lead.status != "Converted"
                or lead.converted_customer_id != customer.customer_id
            ):
                raise DataLoadError(
                    "Customer and lead legacy links do not match."
                )

        for lead in leads.values():
            customer_id = lead.converted_customer_id
            if customer_id is None:
                continue
            customer = customers.get(customer_id)
            if (
                lead.status != "Converted"
                or customer is None
                or customer.source_lead_id != lead.lead_id
            ):
                raise DataLoadError(
                    "Lead and customer legacy links do not match."
                )

    @staticmethod
    def _customer_records(customers):
        return [
            {
                "customer_id": customer.customer_id,
                "name": customer.name,
                "phone": customer.phone,
                "email": customer.email,
                "category": customer.category,
                "source_lead_id": customer.source_lead_id,
            }
            for customer in customers.values()
        ]

    @staticmethod
    def _lead_records(leads):
        return [
            {
                "lead_id": lead.lead_id,
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
                "source": lead.source,
                "status": lead.status,
                "created_at": lead.created_at,
                "notes": lead.notes,
                "follow_up_date": lead.follow_up_date,
                "converted_customer_id": lead.converted_customer_id,
            }
            for lead in leads.values()
        ]

    @staticmethod
    def _atomic_write_json(file_path, records):
        """Write JSON beside the destination and atomically replace it."""
        destination = Path(file_path)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = file.name
                json.dump(records, file, indent=4)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary_path, destination)
            temporary_path = None
        except Exception:
            raise DataSaveError(
                f"Could not safely save data file '{destination.name}'."
            ) from None
        finally:
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass

    def save_customers(self):
        """Save all customers to a TXT file."""
        self._atomic_write_json(
            self.customers_file, self._customer_records(self.customers)
        )

    def save_leads(self):
        """Save all leads to a TXT file."""
        self._atomic_write_json(self.leads_file, self._lead_records(self.leads))

    def add_customer(self, name, phone, email, category="Regular"):
        """Validate and register a customer."""
        self.validate_contact(name, phone, email)

        customer_id = self.next_id("CUST", self.customers)

        customer = Customer(
            customer_id, name, phone, email, category
        )
        self.customers[customer_id] = customer
        try:
            self.save_customers()
        except Exception:
            del self.customers[customer_id]
            raise

        return customer

    def add_lead(self, name, phone, email, source):
        """Validate and register a lead."""
        self.validate_contact(name, phone, email)

        if not source.strip():
            raise ValueError("Lead source cannot be empty.")

        lead_id = self.next_id("LEAD", self.leads)

        lead = Lead(lead_id, name, phone, email, source)
        self.leads[lead_id] = lead
        try:
            self.save_leads()
        except Exception:
            del self.leads[lead_id]
            raise

        return lead

    def update_lead_status(self, lead_id, new_status):
        """Update a lead and persist the change."""
        if lead_id not in self.leads:
            raise ValueError("Lead ID not found.")

        lead = self.leads[lead_id]
        previous_status = lead.status
        lead.update_status(new_status)
        try:
            self.save_leads()
        except Exception:
            lead.status = previous_status
            raise

        return lead

    def add_interaction_note(self, lead_id, interaction_type, description):
        """Add a note to an existing lead and save it."""
        if lead_id not in self.leads:
            raise ValueError("Lead ID not found.")

        note = self.leads[lead_id].add_interaction_note(
            interaction_type, description
        )
        try:
            self.save_leads()
        except Exception:
            self.leads[lead_id].notes.pop()
            raise

        return note

    def set_lead_follow_up(self, lead_id, follow_up_date):
        """Set or clear a lead's follow-up date and persist the change."""
        if lead_id not in self.leads:
            raise ValueError("Lead ID not found.")

        lead = self.leads[lead_id]
        previous_follow_up_date = lead.follow_up_date
        lead.set_follow_up_date(follow_up_date)
        try:
            self.save_leads()
        except Exception:
            lead.follow_up_date = previous_follow_up_date
            raise

        return lead

    @staticmethod
    def _summary_date(today):
        if today is None:
            return date.today()
        if not isinstance(today, date) or isinstance(today, datetime):
            raise ValueError("Summary date must be a date object.")
        return today

    def get_upcoming_follow_ups(self, today=None, within_days=7):
        """Return active leads due today through the configured horizon."""
        if not isinstance(within_days, int) or isinstance(within_days, bool):
            raise ValueError("Follow-up window must be a non-negative integer.")
        if within_days < 0:
            raise ValueError("Follow-up window must be a non-negative integer.")

        current_date = self._summary_date(today)
        last_upcoming_date = current_date + timedelta(days=within_days)
        follow_ups = [
            lead
            for lead in self.leads.values()
            if lead.status not in ("Converted", "Lost")
            and lead.follow_up_date is not None
            and current_date
            <= date.fromisoformat(lead.follow_up_date)
            <= last_upcoming_date
        ]
        return sorted(
            follow_ups,
            key=lambda lead: (lead.follow_up_date, lead.lead_id),
        )

    def get_overdue_follow_ups(self, today=None):
        """Return active leads with follow-up dates earlier than today."""
        current_date = self._summary_date(today)
        follow_ups = [
            lead
            for lead in self.leads.values()
            if lead.status not in ("Converted", "Lost")
            and lead.follow_up_date is not None
            and date.fromisoformat(lead.follow_up_date) < current_date
        ]
        return sorted(
            follow_ups,
            key=lambda lead: (lead.follow_up_date, lead.lead_id),
        )

    def search_customers(self, search_term):
        """Search customers by ID, name, or phone."""
        term = search_term.strip().lower()

        if not term:
            return []

        return [
            customer
            for customer in self.customers.values()
            if term in customer.customer_id.lower()
            or term in customer.name.lower()
            or term in customer.phone
        ]

    def search_leads(self, search_term):
        """Search leads by ID, name, or phone."""
        term = search_term.strip().lower()

        if not term:
            return []

        return [
            lead
            for lead in self.leads.values()
            if term in lead.lead_id.lower()
            or term in lead.name.lower()
            or term in lead.phone
        ]


if __name__ == "__main__":
    print("Start the application with: python -m streamlit run customer_lead_system.py")
