"""Backend tests use only temporary folders and synthetic records."""

import csv
from datetime import date, timedelta
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from customer_lead import CustomerLeadManager, DataLoadError, DataSaveError, FIELDS


class CustomerLeadManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.manager = CustomerLeadManager(self.temp_dir.name)

    def add_customer(self, suffix="1", **values):
        defaults = {"name": f"Test Customer {suffix}", "phone": f"100000{int(suffix):04d}",
                    "email": f"customer{suffix}@example.invalid"}
        defaults.update(values)
        return self.manager.add_customer(**defaults)

    def add_lead(self, suffix="1", **values):
        defaults = {"name": f"Test Lead {suffix}", "phone": f"200000{int(suffix):04d}",
                    "email": f"lead{suffix}@example.invalid", "source": "Website"}
        defaults.update(values)
        return self.manager.add_lead(**defaults)

    def rows(self):
        with self.manager.data_file.open(encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file, delimiter="\t"))

    def test_missing_file_starts_empty_and_saves_tab_separated_text(self):
        self.assertEqual(self.manager.customers, {})
        self.assertEqual(self.manager.leads, {})
        self.assertFalse(self.manager.data_file.exists())
        customer = self.add_customer()
        self.assertEqual(customer.customer_id, "CUST001")
        text = self.manager.data_file.read_text(encoding="utf-8")
        self.assertIn("\t", text)
        self.assertFalse(text.lstrip().startswith("["))
        self.assertEqual(tuple(self.rows()[0]), FIELDS)

    def test_empty_text_file_starts_empty(self):
        self.manager.data_file.write_text("  \n", encoding="utf-8")
        reloaded = CustomerLeadManager(self.temp_dir.name)
        self.assertEqual(reloaded.customers, {})
        self.assertEqual(reloaded.leads, {})

    def test_successful_save_replaces_file_atomically(self):
        with mock.patch("customer_lead.os.replace", wraps=os.replace) as replace:
            customer = self.add_customer()
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(Path(replace.call_args.args[1]), self.manager.data_file)
        self.assertTrue(self.manager.data_file.is_file())
        self.assertEqual(self.rows()[0]["id"], customer.customer_id)
        self.assertEqual(list(Path(self.temp_dir.name).glob(".crm-*.tmp")), [])

    def test_customer_and_lead_ids_advance_after_reload(self):
        self.add_customer()
        self.add_lead()
        manager = CustomerLeadManager(self.temp_dir.name)
        self.assertEqual(manager.add_customer("Another", "1000000002", "another@example.invalid").customer_id, "CUST002")
        self.assertEqual(manager.add_lead("Another Lead", "2000000002", "anotherlead@example.invalid", "Referral").lead_id, "LEAD002")

    def test_contact_validation_and_duplicate_prevention(self):
        with self.assertRaises(ValueError):
            self.manager.add_customer("", "1000000001", "person@example.invalid")
        with self.assertRaises(ValueError):
            self.manager.add_customer("Name", "123", "person@example.invalid")
        with self.assertRaises(ValueError):
            self.manager.add_customer("Name", "1000000001", "bad-email")
        customer = self.add_customer()
        with self.assertRaisesRegex(ValueError, "already uses"):
            self.manager.add_lead("Duplicate", customer.phone, "other@example.invalid", "Referral")
        with self.assertRaisesRegex(ValueError, "already uses"):
            self.manager.add_customer("Duplicate", "1000000002", customer.email)

    def test_customer_search_includes_name_phone_email_and_id(self):
        customer = self.add_customer()
        for term in (customer.customer_id.lower(), "TEST CUSTOMER", customer.phone, customer.email.upper()):
            self.assertEqual(self.manager.search_customers(term), [customer])

    def test_customer_update_segment_filter_and_delete(self):
        customer = self.add_customer()
        self.manager.edit_customer(customer.customer_id, "Updated Name", customer.phone,
                                   customer.email, "Premium")
        self.assertEqual(self.manager.search_customers("updated", "Premium"), [customer])
        self.assertEqual(self.manager.search_customers("updated", "Business"), [])
        self.manager.delete_customer(customer.customer_id)
        self.assertEqual(self.manager.customers, {})
        self.assertEqual(CustomerLeadManager(self.temp_dir.name).customers, {})

    def test_lead_search_status_update_and_validation(self):
        lead = self.add_lead()
        self.manager.update_lead_status(lead.lead_id, "Interested")
        self.assertEqual(self.manager.search_leads(lead.email, "Interested"), [lead])
        other_source = self.add_lead("2", source="Referral")
        self.assertEqual(self.manager.search_leads("", "All statuses", "Referral"), [other_source])
        self.assertEqual(self.manager.search_leads("", "Interested", "Referral"), [])
        with self.assertRaises(ValueError):
            self.manager.update_lead_status(lead.lead_id, "Unknown")
        with self.assertRaises(ValueError):
            self.manager.update_lead_status(lead.lead_id, "Converted")
        self.assertEqual(lead.status, "Interested")

    def test_lead_update_and_delete(self):
        lead = self.add_lead()
        self.manager.edit_lead(lead.lead_id, "Edited lead", lead.phone, lead.email, "Referral")
        self.assertEqual(lead.name, "Edited lead")
        self.assertEqual(lead.source, "Referral")
        self.manager.delete_lead(lead.lead_id)
        self.assertEqual(self.manager.leads, {})

    def test_notes_for_customers_and_leads_persist_and_keep_order(self):
        customer = self.add_customer()
        lead = self.add_lead()
        self.manager.add_interaction_note("customer", customer.customer_id, "Call", "Customer note")
        self.manager.add_interaction_note("lead", lead.lead_id, "Email", "First lead note")
        self.manager.add_interaction_note("lead", lead.lead_id, "Meeting", "Second lead note")
        loaded = CustomerLeadManager(self.temp_dir.name)
        self.assertEqual(len(loaded.customers[customer.customer_id].notes), 1)
        self.assertEqual([n["description"] for n in loaded.leads[lead.lead_id].notes],
                         ["First lead note", "Second lead note"])

    def test_notes_reject_bad_type_empty_text_and_missing_owner(self):
        lead = self.add_lead()
        with self.assertRaises(ValueError):
            self.manager.add_interaction_note("lead", lead.lead_id, "Text", "Note")
        with self.assertRaises(ValueError):
            self.manager.add_interaction_note("lead", lead.lead_id, "Call", " ")
        with self.assertRaises(ValueError):
            self.manager.add_interaction_note("lead", "MISSING", "Call", "Note")

    def test_multiple_follow_ups_update_complete_and_persist(self):
        lead = self.add_lead()
        first = self.manager.add_follow_up("lead", lead.lead_id, "2026-06-01", "Call back")
        second = self.manager.add_follow_up("lead", lead.lead_id, "2026-06-02", "Send quote")
        self.manager.update_follow_up(first["follow_up_id"], "2026-06-03", "Call tomorrow")
        self.manager.complete_follow_up(second["follow_up_id"])
        loaded = CustomerLeadManager(self.temp_dir.name)
        items = loaded.leads[lead.lead_id].follow_ups
        self.assertEqual(items[0]["date"], "2026-06-03")
        self.assertTrue(items[1]["completed"])

    def test_follow_up_classification_and_sorting(self):
        today = date(2026, 6, 10)
        lead_a, lead_b = self.add_lead("1"), self.add_lead("2")
        self.manager.add_follow_up("lead", lead_a.lead_id, (today - timedelta(days=1)).isoformat(), "Overdue")
        self.manager.add_follow_up("lead", lead_b.lead_id, today.isoformat(), "Today")
        self.manager.add_follow_up("lead", lead_a.lead_id, (today + timedelta(days=2)).isoformat(), "Future")
        done = self.manager.add_follow_up("lead", lead_b.lead_id, today.isoformat(), "Done")
        self.manager.complete_follow_up(done["follow_up_id"])
        summary = self.manager.get_follow_up_summary(today)
        self.assertEqual([x["description"] for x in summary["overdue"]], ["Overdue"])
        self.assertEqual([x["description"] for x in summary["today"]], ["Today"])
        self.assertEqual([x["description"] for x in summary["upcoming"]], ["Future"])
        self.assertEqual([x["description"] for x in summary["completed"]], ["Done"])

    def test_follow_up_date_and_description_validation(self):
        lead = self.add_lead()
        for invalid in ("", "2026-02-30", "06/01/2026", "2026-6-1"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.manager.add_follow_up("lead", lead.lead_id, invalid, "Call")
        with self.assertRaises(ValueError):
            self.manager.add_follow_up("lead", lead.lead_id, "2026-06-01", " ")

    def test_follow_up_delete(self):
        customer = self.add_customer()
        item = self.manager.add_follow_up("customer", customer.customer_id, "2026-06-01", "Meeting")
        self.manager.delete_follow_up(item["follow_up_id"])
        self.assertEqual(customer.follow_ups, [])

    def test_conversion_creates_linked_customer_and_preserves_history(self):
        lead = self.add_lead()
        self.manager.add_interaction_note("lead", lead.lead_id, "Call", "Existing note")
        self.manager.add_follow_up("lead", lead.lead_id, "2026-07-01", "Review")
        customer = self.manager.convert_lead(lead.lead_id, "Premium")
        self.manager.edit_customer(customer.customer_id, "Converted customer",
                                   customer.phone, customer.email, "Business")
        self.assertEqual(customer.source_lead_id, lead.lead_id)
        self.assertEqual(lead.converted_customer_id, customer.customer_id)
        self.assertEqual(lead.status, "Converted")
        self.assertEqual(len(lead.notes), 1)
        self.assertEqual(len(lead.follow_ups), 1)
        loaded = CustomerLeadManager(self.temp_dir.name)
        self.assertEqual(loaded.leads[lead.lead_id].status, "Converted")
        self.assertEqual(loaded.customers[customer.customer_id].source_lead_id, lead.lead_id)
        self.assertEqual(loaded.leads[lead.lead_id].converted_customer_id, customer.customer_id)
        self.assertEqual(loaded.leads[lead.lead_id].notes[0]["description"], "Existing note")

    def test_conversion_rejects_duplicate_or_ineligible_leads(self):
        lead = self.add_lead()
        first = self.manager.convert_lead(lead.lead_id)
        with self.assertRaises(ValueError):
            self.manager.convert_lead(lead.lead_id)
        self.assertEqual(len(self.manager.customers), 1)
        self.assertEqual(first.customer_id, "CUST001")
        lost = self.add_lead("2")
        self.manager.update_lead_status(lost.lead_id, "Lost")
        with self.assertRaises(ValueError):
            self.manager.convert_lead(lost.lead_id)

    def test_conversion_save_failure_rolls_back_both_records(self):
        lead = self.add_lead()
        old_bytes = self.manager.data_file.read_bytes()
        with mock.patch("customer_lead.os.replace", side_effect=OSError("synthetic failure")):
            with self.assertRaises(DataSaveError):
                self.manager.convert_lead(lead.lead_id)
        self.assertEqual(self.manager.customers, {})
        self.assertEqual(lead.status, "New")
        self.assertIsNone(lead.converted_customer_id)
        self.assertEqual(self.manager.data_file.read_bytes(), old_bytes)

    def test_save_failure_keeps_previous_text_and_removes_temp_file(self):
        self.add_customer()
        old_bytes = self.manager.data_file.read_bytes()
        with mock.patch("customer_lead.os.replace", side_effect=OSError("synthetic failure")):
            with self.assertRaises(DataSaveError):
                self.add_lead()
        self.assertEqual(self.manager.leads, {})
        self.assertEqual(self.manager.data_file.read_bytes(), old_bytes)
        self.assertEqual(list(Path(self.temp_dir.name).glob(".crm-*.tmp")), [])

    def test_malformed_or_invalid_file_does_not_partially_load(self):
        self.add_customer()
        self.manager.data_file.write_text("not a tab-separated record", encoding="utf-8")
        fresh = CustomerLeadManager.__new__(CustomerLeadManager)
        fresh.data_file = self.manager.data_file
        original = {"sentinel": object()}
        fresh.customers, fresh.leads = original, original
        with self.assertRaises(DataLoadError):
            fresh.load_data()
        self.assertIs(fresh.customers, original)
        self.assertIs(fresh.leads, original)

    def test_invalid_owner_link_is_rejected_on_reload(self):
        lead = self.add_lead()
        self.manager.add_interaction_note("lead", lead.lead_id, "Call", "Synthetic note")
        rows = self.rows()
        rows[-1]["related_id"] = "MISSING"
        with self.manager.data_file.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        with self.assertRaises(DataLoadError):
            CustomerLeadManager(self.temp_dir.name)

    def test_legacy_converted_pair_is_read_from_text_rows(self):
        lead = self.add_lead()
        customer = self.manager.convert_lead(lead.lead_id)
        reloaded = CustomerLeadManager(self.temp_dir.name)
        self.assertEqual(reloaded.leads[lead.lead_id].status, "Converted")
        self.assertEqual(reloaded.customers[customer.customer_id].source_lead_id, lead.lead_id)


if __name__ == "__main__":
    unittest.main()
