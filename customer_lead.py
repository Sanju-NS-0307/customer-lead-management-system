
"""
Customer and Lead Management System
Core Python backend with TXT file persistence.
"""

import json
import os
from datetime import datetime


class Customer:
    """Stores information about a registered customer."""

    def __init__(
        self, customer_id, name, phone, email, category="Regular"
    ):
        self.customer_id = customer_id
        self.name = name.strip()
        self.phone = phone.strip()
        self.email = email.strip()
        self.category = category

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

    def update_status(self, new_status):
        """Update the lead's status after validating it."""
        if new_status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid status. Choose from: {', '.join(self.VALID_STATUSES)}"
            )

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


class CustomerLeadManager:
    """Manages customers, leads, and TXT file storage."""

    def __init__(self):
        self.customers = {}
        self.leads = {}

        self.customers_file = "customers.txt"
        self.leads_file = "leads.txt"

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
        """Load existing records from TXT files."""
        if os.path.exists(self.customers_file):
            try:
                with open(
                    self.customers_file, "r", encoding="utf-8"
                ) as file:
                    records = json.load(file)

                for record in records:
                    customer = Customer(**record)
                    self.customers[customer.customer_id] = customer

            except (json.JSONDecodeError, TypeError, KeyError) as error:
                print("Could not load customer data:", error)

        if os.path.exists(self.leads_file):
            try:
                with open(
                    self.leads_file, "r", encoding="utf-8"
                ) as file:
                    records = json.load(file)

                for record in records:
                    lead = Lead(
                        record["lead_id"],
                        record["name"],
                        record["phone"],
                        record["email"],
                        record["source"],
                        record["status"],
                    )
                    lead.created_at = record["created_at"]
                    self.leads[lead.lead_id] = lead

            except (json.JSONDecodeError, TypeError, KeyError) as error:
                print("Could not load lead data:", error)

    def save_customers(self):
        """Save all customers to a TXT file."""
        records = [
            {
                "customer_id": customer.customer_id,
                "name": customer.name,
                "phone": customer.phone,
                "email": customer.email,
                "category": customer.category,
            }
            for customer in self.customers.values()
        ]

        with open(
            self.customers_file, "w", encoding="utf-8"
        ) as file:
            json.dump(records, file, indent=4)

    def save_leads(self):
        """Save all leads to a TXT file."""
        records = [
            {
                "lead_id": lead.lead_id,
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
                "source": lead.source,
                "status": lead.status,
                "created_at": lead.created_at,
            }
            for lead in self.leads.values()
        ]

        with open(self.leads_file, "w", encoding="utf-8") as file:
            json.dump(records, file, indent=4)

    def add_customer(self, name, phone, email, category="Regular"):
        """Validate and register a customer."""
        self.validate_contact(name, phone, email)

        customer_id = self.next_id("CUST", self.customers)

        customer = Customer(
            customer_id, name, phone, email, category
        )
        self.customers[customer_id] = customer
        self.save_customers()

        return customer

    def add_lead(self, name, phone, email, source):
        """Validate and register a lead."""
        self.validate_contact(name, phone, email)

        if not source.strip():
            raise ValueError("Lead source cannot be empty.")

        lead_id = self.next_id("LEAD", self.leads)

        lead = Lead(lead_id, name, phone, email, source)
        self.leads[lead_id] = lead
        self.save_leads()

        return lead

    def update_lead_status(self, lead_id, new_status):
        """Update a lead and persist the change."""
        if lead_id not in self.leads:
            raise ValueError("Lead ID not found.")

        self.leads[lead_id].update_status(new_status)
        self.save_leads()

        return self.leads[lead_id]

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
    manager = CustomerLeadManager()

    print("=== CUSTOMER REGISTRATION ===")
    customer = manager.add_customer(
        "Rahul Kumar",
        "9876543210",
        "rahul@example.com",
    )
    print(customer.display_details())

    print("\n=== LEAD REGISTRATION ===")
    lead = manager.add_lead(
        "Priya Sharma",
        "9876501234",
        "priya@example.com",
        "Website",
    )
    print(lead.display_details())

    print("\n=== CUSTOMER SEARCH ===")
    for result in manager.search_customers("Rahul"):
        print(result.customer_id, "-", result.name)

    print("\n=== UPDATE LEAD STATUS ===")
    updated_lead = manager.update_lead_status(
        lead.lead_id, "Interested"
    )
    print(updated_lead.lead_id, "-", updated_lead.status)

    print("\n=== VALIDATION TEST ===")
    try:
        manager.add_customer(
            "Test User",
            "123",
            "test@example.com",
        )
    except ValueError as error:
        print("Validation works:", error)

    print("\nData saved to customers.txt and leads.txt.")
