"""Customer and Lead Management System with local TSV text storage."""

import csv
import os
from datetime import date, datetime
from pathlib import Path
import tempfile


STATUSES = ("New", "Contacted", "Interested", "Converted", "Lost")
INTERACTION_TYPES = ("Call", "Email", "Meeting", "Other")
SEGMENTS = ("Regular", "Premium", "Business")
FIELDS = (
    "type", "id", "related_id", "name", "phone", "email", "category",
    "source", "status", "created_at", "date", "interaction_type",
    "description", "completed",
)


class Customer:
    """Store one customer and its notes and follow-up reminders."""

    def __init__(self, customer_id, name, phone, email, category="Regular",
                 source_lead_id=None):
        self.customer_id = customer_id
        self.name = name.strip()
        self.phone = phone.strip()
        self.email = email.strip()
        self.category = category
        self.source_lead_id = source_lead_id
        self.notes = []
        self.follow_ups = []

    def display_details(self):
        return (f"Customer ID: {self.customer_id}\nName: {self.name}\n"
                f"Phone: {self.phone}\nEmail: {self.email}\n"
                f"Category: {self.category}")


class Lead:
    """Store one potential customer and its activity history."""

    VALID_STATUSES = list(STATUSES)
    VALID_INTERACTION_TYPES = list(INTERACTION_TYPES)

    def __init__(self, lead_id, name, phone, email, source, status="New",
                 notes=None, follow_up_date=None, converted_customer_id=None):
        if status not in STATUSES:
            raise ValueError("Choose a valid lead status.")
        self.lead_id = lead_id
        self.name = name.strip()
        self.phone = phone.strip()
        self.email = email.strip()
        self.source = source.strip()
        self.status = status
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.notes = list(notes or [])
        self.follow_ups = []
        # These attributes keep old in-memory callers working.
        self.follow_up_date = follow_up_date
        self.converted_customer_id = converted_customer_id

    def update_status(self, status):
        if status not in STATUSES:
            raise ValueError("Choose a valid lead status.")
        if self.status == "Converted" and status != "Converted":
            raise ValueError("A converted lead cannot change to another status.")
        self.status = status

    def display_details(self):
        return (f"Lead ID: {self.lead_id}\nName: {self.name}\n"
                f"Phone: {self.phone}\nEmail: {self.email}\n"
                f"Source: {self.source}\nStatus: {self.status}")


class DataLoadError(ValueError):
    """Raised when the local data file has an invalid format or record."""


class DataSaveError(OSError):
    """Raised when the local data file cannot be safely saved."""


class CustomerLeadManager:
    """Manage records stored as tab-separated rows in one TXT file."""

    def __init__(self, data_dir=None):
        folder = Path(data_dir) if data_dir else Path(__file__).resolve().parent
        self.data_file = folder / "customer_lead_data.txt"
        self.customers = {}
        self.leads = {}
        self.load_data()

    @staticmethod
    def validate_contact(name, phone, email):
        if not name or not name.strip():
            raise ValueError("Name cannot be empty.")
        phone = (phone or "").strip()
        if not phone.isdigit() or len(phone) != 10:
            raise ValueError("Phone number must contain exactly 10 digits.")
        email = (email or "").strip()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise ValueError("Please enter a valid email address.")

    @staticmethod
    def _valid_date(value):
        try:
            return date.fromisoformat(value).isoformat() == value
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _next_id(prefix, records):
        numbers = [int(key[len(prefix):]) for key in records
                   if key.startswith(prefix) and key[len(prefix):].isdigit()]
        return f"{prefix}{max(numbers, default=0) + 1:03d}"

    def load_data(self):
        """Read and validate every row before changing manager state."""
        customers, leads = {}, {}
        rows = []
        if self.data_file.exists():
            try:
                with self.data_file.open("r", encoding="utf-8", newline="") as file:
                    if file.read().strip():
                        file.seek(0)
                        reader = csv.DictReader(file, delimiter="\t")
                        if reader.fieldnames != list(FIELDS):
                            raise DataLoadError("The local data file has an unsupported format.")
                        rows = list(reader)
                    if any(None in row for row in rows):
                        raise DataLoadError("The local data file contains an invalid row.")
            except DataLoadError:
                raise
            except (OSError, UnicodeError, csv.Error):
                raise DataLoadError("Could not read the local data file.") from None

        # Create all customers and leads first; activity rows can then link to either.
        try:
            for row in rows:
                kind, record_id = row["type"], row["id"]
                if kind == "customer":
                    if not record_id or record_id in customers:
                        raise ValueError
                    customer = Customer(record_id, row["name"], row["phone"],
                                        row["email"], row["category"] or "Regular",
                                        row["related_id"] or None)
                    self.validate_contact(customer.name, customer.phone, customer.email)
                    if customer.category not in SEGMENTS:
                        raise ValueError
                    customers[record_id] = customer
                elif kind == "lead":
                    if not record_id or record_id in leads or row["status"] not in STATUSES:
                        raise ValueError
                    lead = Lead(record_id, row["name"], row["phone"], row["email"],
                                row["source"], row["status"],
                                converted_customer_id=row["related_id"] or None)
                    self.validate_contact(lead.name, lead.phone, lead.email)
                    if not lead.source:
                        raise ValueError
                    lead.created_at = row["created_at"]
                    leads[record_id] = lead
                elif kind not in ("note", "follow_up"):
                    raise ValueError

            follow_up_ids = set()
            for row in rows:
                kind = row["type"]
                if kind not in ("note", "follow_up"):
                    continue
                owner = customers.get(row["related_id"]) or leads.get(row["related_id"])
                if owner is None:
                    raise ValueError
                if kind == "note":
                    if (row["interaction_type"] not in INTERACTION_TYPES
                            or not row["description"] or not self._valid_date(row["date"])):
                        raise ValueError
                    owner.notes.append({"date": row["date"],
                                        "interaction_type": row["interaction_type"],
                                        "description": row["description"]})
                else:
                    if (not row["id"] or row["id"] in follow_up_ids
                            or not self._valid_date(row["date"])
                            or row["completed"] not in ("true", "false")):
                        raise ValueError
                    follow_up_ids.add(row["id"])
                    owner.follow_ups.append({"follow_up_id": row["id"],
                                             "date": row["date"],
                                             "description": row["description"],
                                             "completed": row["completed"] == "true"})

            self._check_loaded_duplicates(customers, leads)
            self._check_conversion_links(customers, leads)
        except (KeyError, TypeError, ValueError):
            raise DataLoadError("The local data file contains an invalid record.") from None

        self.customers, self.leads = customers, leads

    @staticmethod
    def _check_loaded_duplicates(customers, leads):
        records = list(customers.values()) + list(leads.values())
        for index, record in enumerate(records):
            for other in records[index + 1:]:
                same_contact = (record.phone == other.phone
                                or record.email.casefold() == other.email.casefold())
                if not same_contact:
                    continue
                customer = record if isinstance(record, Customer) else other if isinstance(other, Customer) else None
                lead = record if isinstance(record, Lead) else other if isinstance(other, Lead) else None
                is_conversion_pair = (
                    customer is not None and lead is not None
                    and customer.source_lead_id == lead.lead_id
                    and lead.converted_customer_id == customer.customer_id
                    and lead.status == "Converted"
                )
                if not is_conversion_pair:
                    raise DataLoadError("The local data file contains duplicate contacts.")

    @staticmethod
    def _check_conversion_links(customers, leads):
        for lead in leads.values():
            if lead.converted_customer_id:
                customer = customers.get(lead.converted_customer_id)
                if (lead.status != "Converted" or customer is None
                        or customer.source_lead_id != lead.lead_id):
                    raise DataLoadError("Converted customer and lead links do not match.")
        for customer in customers.values():
            if customer.source_lead_id:
                lead = leads.get(customer.source_lead_id)
                if lead is None or lead.converted_customer_id != customer.customer_id:
                    raise DataLoadError("Converted customer and lead links do not match.")

    def _rows(self):
        rows = []
        for customer in self.customers.values():
            rows.append(self._row(type="customer", id=customer.customer_id,
                                  related_id=customer.source_lead_id or "",
                                  name=customer.name, phone=customer.phone,
                                  email=customer.email, category=customer.category))
        for lead in self.leads.values():
            rows.append(self._row(type="lead", id=lead.lead_id,
                                  related_id=lead.converted_customer_id or "",
                                  name=lead.name, phone=lead.phone, email=lead.email,
                                  source=lead.source, status=lead.status,
                                  created_at=lead.created_at))
        for owner in list(self.customers.values()) + list(self.leads.values()):
            owner_id = getattr(owner, "customer_id", getattr(owner, "lead_id", ""))
            for note in owner.notes:
                rows.append(self._row(type="note", id="NOTE", related_id=owner_id,
                                      date=note["date"],
                                      interaction_type=note["interaction_type"],
                                      description=note["description"]))
            for item in owner.follow_ups:
                rows.append(self._row(type="follow_up", id=item["follow_up_id"],
                                      related_id=owner_id, date=item["date"],
                                      description=item["description"],
                                      completed=str(item["completed"]).lower()))
        return rows

    @staticmethod
    def _row(**values):
        row = dict.fromkeys(FIELDS, "")
        row.update(values)
        return row

    def save_data(self):
        """Write a complete temporary file, then replace the old file atomically."""
        temporary = None
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="",
                    dir=self.data_file.parent, prefix=".crm-", suffix=".tmp",
                    delete=False) as file:
                temporary = file.name
                writer = csv.DictWriter(file, fieldnames=FIELDS, delimiter="\t",
                                        lineterminator="\n")
                writer.writeheader()
                writer.writerows(self._rows())
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.data_file)
            temporary = None
        except Exception:
            raise DataSaveError("Could not safely save the local data file.") from None
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def _save_or_rollback(self, rollback):
        try:
            self.save_data()
        except Exception:
            rollback()
            raise

    def _check_duplicate_contact(self, phone, email, skip_id=None):
        for record in list(self.customers.values()) + list(self.leads.values()):
            record_id = getattr(record, "customer_id", getattr(record, "lead_id", None))
            if record_id != skip_id and (record.phone == phone.strip()
                    or record.email.casefold() == email.strip().casefold()):
                if (skip_id is not None and (
                        isinstance(record, Lead) and record.converted_customer_id == skip_id
                        or isinstance(record, Customer) and record.source_lead_id == skip_id)):
                    continue
                raise ValueError("A customer or lead already uses that phone or email.")

    def add_customer(self, name, phone, email, category="Regular"):
        self.validate_contact(name, phone, email)
        if category not in SEGMENTS:
            raise ValueError("Choose a valid customer segment.")
        self._check_duplicate_contact(phone, email)
        record = Customer(self._next_id("CUST", self.customers), name, phone, email, category)
        self.customers[record.customer_id] = record
        self._save_or_rollback(lambda: self.customers.pop(record.customer_id, None))
        return record

    def edit_customer(self, customer_id, name, phone, email, category):
        record = self.customers.get(customer_id)
        if record is None:
            raise ValueError("Customer ID not found.")
        self.validate_contact(name, phone, email)
        if category not in SEGMENTS:
            raise ValueError("Choose a valid customer segment.")
        self._check_duplicate_contact(phone, email, customer_id)
        old = record.name, record.phone, record.email, record.category
        record.name, record.phone, record.email, record.category = (
            name.strip(), phone.strip(), email.strip(), category)
        self._save_or_rollback(lambda: self._restore_customer(record, old))
        return record

    @staticmethod
    def _restore_customer(record, values):
        record.name, record.phone, record.email, record.category = values

    def delete_customer(self, customer_id):
        record = self.customers.get(customer_id)
        if record is None:
            raise ValueError("Customer ID not found.")
        if record.source_lead_id:
            raise ValueError("A customer linked to a converted lead cannot be deleted.")
        del self.customers[customer_id]
        self._save_or_rollback(lambda: self.customers.__setitem__(customer_id, record))

    def add_lead(self, name, phone, email, source):
        self.validate_contact(name, phone, email)
        if not source or not source.strip():
            raise ValueError("Lead source cannot be empty.")
        self._check_duplicate_contact(phone, email)
        record = Lead(self._next_id("LEAD", self.leads), name, phone, email, source)
        self.leads[record.lead_id] = record
        self._save_or_rollback(lambda: self.leads.pop(record.lead_id, None))
        return record

    def edit_lead(self, lead_id, name, phone, email, source):
        record = self.leads.get(lead_id)
        if record is None:
            raise ValueError("Lead ID not found.")
        if record.status == "Converted":
            raise ValueError("A converted lead cannot be edited.")
        self.validate_contact(name, phone, email)
        if not source or not source.strip():
            raise ValueError("Lead source cannot be empty.")
        self._check_duplicate_contact(phone, email, lead_id)
        old = record.name, record.phone, record.email, record.source
        record.name, record.phone, record.email, record.source = (
            name.strip(), phone.strip(), email.strip(), source.strip())
        self._save_or_rollback(lambda: self._restore_lead(record, old))
        return record

    @staticmethod
    def _restore_lead(record, values):
        record.name, record.phone, record.email, record.source = values

    def delete_lead(self, lead_id):
        record = self.leads.get(lead_id)
        if record is None:
            raise ValueError("Lead ID not found.")
        if record.status == "Converted":
            raise ValueError("A converted lead cannot be deleted.")
        del self.leads[lead_id]
        self._save_or_rollback(lambda: self.leads.__setitem__(lead_id, record))

    def update_lead_status(self, lead_id, status):
        record = self.leads.get(lead_id)
        if record is None:
            raise ValueError("Lead ID not found.")
        if status == "Converted":
            raise ValueError("Use lead conversion to set Converted status.")
        old = record.status
        record.update_status(status)
        self._save_or_rollback(lambda: setattr(record, "status", old))
        return record

    def convert_lead(self, lead_id, category="Regular"):
        lead = self.leads.get(lead_id)
        if lead is None:
            raise ValueError("Lead ID not found.")
        if lead.status not in ("New", "Contacted", "Interested"):
            raise ValueError("Only active leads can be converted.")
        if category not in SEGMENTS:
            raise ValueError("Choose a valid customer segment.")
        customer = Customer(self._next_id("CUST", self.customers), lead.name,
                            lead.phone, lead.email, category, lead_id)
        old_status, old_link = lead.status, lead.converted_customer_id
        self.customers[customer.customer_id] = customer
        lead.status, lead.converted_customer_id = "Converted", customer.customer_id

        def rollback():
            self.customers.pop(customer.customer_id, None)
            lead.status, lead.converted_customer_id = old_status, old_link

        self._save_or_rollback(rollback)
        return customer

    def search_customers(self, search_term="", category="All segments"):
        term = (search_term or "").strip().casefold()
        return [record for record in self.customers.values()
                if (category == "All segments" or record.category == category)
                and (not term or any(term in value.casefold() for value in
                     (record.customer_id, record.name, record.phone, record.email)))]

    def search_leads(self, search_term="", status="All statuses", source="All sources"):
        term = (search_term or "").strip().casefold()
        return [record for record in self.leads.values()
                if (status == "All statuses" or record.status == status)
                and (source == "All sources" or record.source == source)
                and (not term or any(term in value.casefold() for value in
                     (record.lead_id, record.name, record.phone, record.email, record.source)))]

    def add_interaction_note(self, record_type, record_id, interaction_type, description):
        collection = self.customers if record_type == "customer" else self.leads if record_type == "lead" else None
        if collection is None or record_id not in collection:
            raise ValueError("Customer or lead ID not found.")
        if interaction_type not in INTERACTION_TYPES:
            raise ValueError("Choose a valid interaction type.")
        if not description or not description.strip():
            raise ValueError("Interaction description cannot be empty.")
        owner = collection[record_id]
        note = {"date": date.today().isoformat(), "interaction_type": interaction_type,
                "description": description.strip()}
        owner.notes.append(note)
        self._save_or_rollback(lambda: owner.notes.pop())
        return note

    def add_follow_up(self, record_type, record_id, due_date, description):
        collection = self.customers if record_type == "customer" else self.leads if record_type == "lead" else None
        if collection is None or record_id not in collection:
            raise ValueError("Customer or lead ID not found.")
        if not self._valid_date(due_date):
            raise ValueError("Follow-up date must use YYYY-MM-DD.")
        if not description or not description.strip():
            raise ValueError("Follow-up description cannot be empty.")
        owner = collection[record_id]
        all_items = [item for entity in list(self.customers.values()) + list(self.leads.values())
                     for item in entity.follow_ups]
        item = {"follow_up_id": self._next_id("FUP", {entry["follow_up_id"]: entry for entry in all_items}),
                "date": due_date, "description": description.strip(), "completed": False}
        owner.follow_ups.append(item)
        self._save_or_rollback(lambda: owner.follow_ups.pop())
        return item

    def _find_follow_up(self, follow_up_id):
        for owner in list(self.customers.values()) + list(self.leads.values()):
            for item in owner.follow_ups:
                if item["follow_up_id"] == follow_up_id:
                    return owner, item
        raise ValueError("Follow-up ID not found.")

    def update_follow_up(self, follow_up_id, due_date, description):
        if not self._valid_date(due_date):
            raise ValueError("Follow-up date must use YYYY-MM-DD.")
        if not description or not description.strip():
            raise ValueError("Follow-up description cannot be empty.")
        _, item = self._find_follow_up(follow_up_id)
        old = item["date"], item["description"]
        item["date"], item["description"] = due_date, description.strip()
        self._save_or_rollback(lambda: self._restore_follow_up(item, old))
        return item

    @staticmethod
    def _restore_follow_up(item, values):
        item["date"], item["description"] = values

    def complete_follow_up(self, follow_up_id, completed=True):
        _, item = self._find_follow_up(follow_up_id)
        old = item["completed"]
        item["completed"] = bool(completed)
        self._save_or_rollback(lambda: item.__setitem__("completed", old))
        return item

    def delete_follow_up(self, follow_up_id):
        owner, item = self._find_follow_up(follow_up_id)
        index = owner.follow_ups.index(item)
        owner.follow_ups.pop(index)
        self._save_or_rollback(lambda: owner.follow_ups.insert(index, item))

    def get_follow_up_summary(self, today=None):
        current = today or date.today()
        if not isinstance(current, date) or isinstance(current, datetime):
            raise ValueError("Summary date must be a date object.")
        summary = {name: [] for name in ("overdue", "today", "upcoming", "completed")}
        for owner_type, collection in (("customer", self.customers), ("lead", self.leads)):
            for owner in collection.values():
                owner_id = getattr(owner, "customer_id", getattr(owner, "lead_id", ""))
                for item in owner.follow_ups:
                    entry = dict(item, owner_type=owner_type, owner_id=owner_id,
                                 name=owner.name, status=getattr(owner, "status", "Customer"))
                    if item["completed"]:
                        group = "completed"
                    elif date.fromisoformat(item["date"]) < current:
                        group = "overdue"
                    elif date.fromisoformat(item["date"]) == current:
                        group = "today"
                    else:
                        group = "upcoming"
                    summary[group].append(entry)
        for items in summary.values():
            items.sort(key=lambda item: (item["date"], item["owner_id"], item["follow_up_id"]))
        return summary

    # Simple helpers for older callers that used one follow-up date per lead.
    def set_lead_follow_up(self, lead_id, due_date):
        lead = self.leads.get(lead_id)
        if lead is None:
            raise ValueError("Lead ID not found.")
        existing = next((item for item in lead.follow_ups if item["description"] == "Follow-up"), None)
        if due_date is None:
            if existing:
                self.delete_follow_up(existing["follow_up_id"])
            lead.follow_up_date = None
            return lead
        if not self._valid_date(due_date):
            raise ValueError("Follow-up date must use YYYY-MM-DD.")
        if existing:
            self.update_follow_up(existing["follow_up_id"], due_date, "Follow-up")
        else:
            self.add_follow_up("lead", lead_id, due_date, "Follow-up")
        lead.follow_up_date = due_date
        return lead

    def get_upcoming_follow_ups(self, today=None, within_days=7):
        current = today or date.today()
        end = date.fromordinal(current.toordinal() + within_days)
        return [item for item in self.get_follow_up_summary(current)["today"]
                + self.get_follow_up_summary(current)["upcoming"]
                if date.fromisoformat(item["date"]) <= end]

    def get_overdue_follow_ups(self, today=None):
        return self.get_follow_up_summary(today)["overdue"]


if __name__ == "__main__":
    print("Start the application with: python -m streamlit run customer_lead_system.py")
