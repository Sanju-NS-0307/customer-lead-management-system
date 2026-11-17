"""Isolated backend tests for the customer and lead manager."""

import contextlib
from datetime import date, datetime
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import customer_lead
from customer_lead import CustomerLeadManager, DataLoadError, DataSaveError


class CustomerLeadManagerTests(unittest.TestCase):
    """Exercise manager behavior using files in a temporary directory."""

    def setUp(self):
        self.original_cwd = Path.cwd()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._restore_cwd_and_cleanup)
        os.chdir(self.temp_dir.name)
        self.manager = CustomerLeadManager(data_dir=self.temp_dir.name)

    def _restore_cwd_and_cleanup(self):
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def write_json(self, filename, records):
        Path(filename).write_text(
            json.dumps(records, indent=4), encoding="utf-8"
        )

    def test_customer_registration_persists_and_trims_fields(self):
        customer = self.manager.add_customer(
            "  Test Customer  ",
            "0000000001",
            "customer@example.invalid",
            "Premium",
        )

        self.assertEqual(customer.customer_id, "CUST001")
        self.assertEqual(customer.name, "Test Customer")
        self.assertEqual(customer.phone, "0000000001")
        self.assertEqual(customer.email, "customer@example.invalid")
        self.assertEqual(customer.category, "Premium")
        records = json.loads(Path("customers.txt").read_text(encoding="utf-8"))
        self.assertEqual(records[0]["customer_id"], customer.customer_id)

    def test_lead_registration_persists_with_new_status(self):
        lead = self.manager.add_lead(
            "Test Lead", "0000000002", "lead@example.invalid", "Referral"
        )

        self.assertEqual(lead.lead_id, "LEAD001")
        self.assertEqual(lead.status, "New")
        records = json.loads(Path("leads.txt").read_text(encoding="utf-8"))
        self.assertEqual(records[0]["lead_id"], lead.lead_id)
        self.assertEqual(records[0]["status"], "New")

    def test_automatic_ids_advance_after_existing_ids(self):
        self.write_json(
            "customers.txt",
            [
                {
                    "customer_id": "CUST009",
                    "name": "Seed Customer",
                    "phone": "0000000003",
                    "email": "seed-customer@example.invalid",
                    "category": "Regular",
                }
            ],
        )
        self.write_json(
            "leads.txt",
            [
                {
                    "lead_id": "LEAD012",
                    "name": "Seed Lead",
                    "phone": "0000000004",
                    "email": "seed-lead@example.invalid",
                    "source": "Website",
                    "status": "New",
                    "created_at": "2026-01-01 10:00",
                }
            ],
        )
        manager = CustomerLeadManager(data_dir=self.temp_dir.name)

        customer = manager.add_customer(
            "Next Customer", "0000000005", "next-customer@example.invalid"
        )
        lead = manager.add_lead(
            "Next Lead", "0000000006", "next-lead@example.invalid", "Other"
        )

        self.assertEqual(customer.customer_id, "CUST010")
        self.assertEqual(lead.lead_id, "LEAD013")

    def test_invalid_customer_inputs_are_rejected(self):
        invalid_contacts = (
            ("  ", "0000000001", "person@example.invalid"),
            ("Test Customer", "123", "person@example.invalid"),
            ("Test Customer", "000000000x", "person@example.invalid"),
            ("Test Customer", "0000000001", "not-an-email"),
        )

        for name, phone, email in invalid_contacts:
            with self.subTest(name=name, phone=phone, email=email):
                with self.assertRaises(ValueError):
                    self.manager.add_customer(name, phone, email)

        self.assertEqual(self.manager.customers, {})
        self.assertFalse(Path("customers.txt").exists())

    def test_invalid_lead_inputs_are_rejected(self):
        invalid_contacts = (
            ("", "0000000001", "person@example.invalid", "Website"),
            ("Test Lead", "123", "person@example.invalid", "Website"),
            ("Test Lead", "0000000001", "not-an-email", "Website"),
            ("Test Lead", "0000000001", "person@example.invalid", "  "),
        )

        for name, phone, email, source in invalid_contacts:
            with self.subTest(name=name, phone=phone, email=email, source=source):
                with self.assertRaises(ValueError):
                    self.manager.add_lead(name, phone, email, source)

        self.assertEqual(self.manager.leads, {})
        self.assertFalse(Path("leads.txt").exists())

    def test_valid_lead_status_update_is_returned_and_persisted(self):
        lead = self.manager.add_lead(
            "Status Lead", "0000000007", "status@example.invalid", "Website"
        )

        updated = self.manager.update_lead_status(lead.lead_id, "Interested")
        records = json.loads(Path("leads.txt").read_text(encoding="utf-8"))

        self.assertIs(updated, lead)
        self.assertEqual(lead.status, "Interested")
        self.assertEqual(records[0]["status"], "Interested")

    def test_invalid_lead_status_is_rejected_without_changing_status(self):
        lead = self.manager.add_lead(
            "Status Lead", "0000000008", "status2@example.invalid", "Website"
        )

        with self.assertRaises(ValueError):
            self.manager.update_lead_status(lead.lead_id, "Unknown")
        with self.assertRaises(ValueError):
            self.manager.update_lead_status(lead.lead_id, "Converted")

        self.assertEqual(lead.status, "New")

    def test_customer_search_matches_id_name_and_phone_case_insensitively(self):
        customer = self.manager.add_customer(
            "Search Customer", "0000000009", "search-customer@example.invalid"
        )

        self.assertEqual(
            [item.customer_id for item in self.manager.search_customers("cust001")],
            [customer.customer_id],
        )
        self.assertEqual(
            [item.customer_id for item in self.manager.search_customers("SEARCH")],
            [customer.customer_id],
        )
        self.assertEqual(
            [item.customer_id for item in self.manager.search_customers("0000000009")],
            [customer.customer_id],
        )
        self.assertEqual(self.manager.search_customers("  "), [])

    def test_lead_search_matches_id_name_and_phone_case_insensitively(self):
        lead = self.manager.add_lead(
            "Search Lead", "0000000010", "search-lead@example.invalid", "Website"
        )

        self.assertEqual(
            [item.lead_id for item in self.manager.search_leads("lead001")],
            [lead.lead_id],
        )
        self.assertEqual(
            [item.lead_id for item in self.manager.search_leads("SEARCH")],
            [lead.lead_id],
        )
        self.assertEqual(
            [item.lead_id for item in self.manager.search_leads("0000000010")],
            [lead.lead_id],
        )
        self.assertEqual(self.manager.search_leads("  "), [])

    def test_multiple_interaction_notes_are_added_to_one_lead(self):
        lead = self.manager.add_lead(
            "Notes Lead", "0000000011", "notes@example.invalid", "Referral"
        )

        first = self.manager.add_interaction_note(
            lead.lead_id, "Call", "Initial discussion"
        )
        second = self.manager.add_interaction_note(
            lead.lead_id, "Meeting", "Product walkthrough"
        )

        self.assertEqual(len(lead.notes), 2)
        self.assertEqual(first["interaction_type"], "Call")
        self.assertEqual(second["interaction_type"], "Meeting")
        expected_fields = {"date", "interaction_type", "description"}
        self.assertTrue(all(set(note) == expected_fields for note in lead.notes))

    def test_interaction_notes_persist_and_reload_in_fresh_manager(self):
        lead = self.manager.add_lead(
            "Reload Lead", "0000000012", "reload@example.invalid", "Referral"
        )
        self.manager.add_interaction_note(
            lead.lead_id, "Email", "Sent requested information"
        )

        reloaded_manager = CustomerLeadManager(data_dir=self.temp_dir.name)

        self.assertEqual(reloaded_manager.leads[lead.lead_id].notes, lead.notes)

    def test_legacy_lead_without_notes_loads_with_empty_notes(self):
        self.write_json(
            "leads.txt",
            [
                {
                    "lead_id": "LEAD004",
                    "name": "Legacy Lead",
                    "phone": "0000000013",
                    "email": "legacy@example.invalid",
                    "source": "Website",
                    "status": "New",
                    "created_at": "2026-01-01 10:00",
                }
            ],
        )

        manager = CustomerLeadManager(data_dir=self.temp_dir.name)

        self.assertEqual(manager.leads["LEAD004"].notes, [])
        self.assertIsNone(manager.leads["LEAD004"].follow_up_date)

    def test_missing_data_files_start_empty_and_are_created_on_registration(self):
        self.assertEqual(self.manager.customers, {})
        self.assertEqual(self.manager.leads, {})
        self.assertFalse(Path("customers.txt").exists())
        self.assertFalse(Path("leads.txt").exists())

        self.manager.add_customer(
            "Created Customer", "0000000014", "created-customer@example.invalid"
        )
        self.manager.add_lead(
            "Created Lead", "0000000015", "created-lead@example.invalid", "Website"
        )

        self.assertTrue(Path("customers.txt").is_file())
        self.assertTrue(Path("leads.txt").is_file())

    def test_empty_data_files_are_handled_without_crashing(self):
        Path("customers.txt").write_text("", encoding="utf-8")
        Path("leads.txt").write_text("", encoding="utf-8")

        with contextlib.redirect_stdout(io.StringIO()):
            manager = CustomerLeadManager(data_dir=self.temp_dir.name)

        self.assertEqual(manager.customers, {})
        self.assertEqual(manager.leads, {})

    def assert_no_temporary_files(self):
        temporary_files = list(Path(self.temp_dir.name).glob(".*.tmp"))
        self.assertEqual(temporary_files, [])

    def test_successful_save_uses_atomic_replacement(self):
        with mock.patch(
            "customer_lead.os.replace", wraps=os.replace
        ) as replace:
            customer = self.manager.add_customer(
                "Atomic Customer",
                "0000000017",
                "atomic@example.invalid",
            )

        self.assertEqual(replace.call_count, 1)
        temporary_path, destination_path = replace.call_args.args
        self.assertEqual(Path(temporary_path).parent, Path(self.manager.customers_file).parent)
        self.assertEqual(Path(destination_path), Path(self.manager.customers_file))
        self.assertTrue(Path(self.manager.customers_file).is_file())
        self.assertEqual(customer.customer_id, "CUST001")
        self.assert_no_temporary_files()

    def test_failed_customer_save_preserves_disk_and_rolls_back_memory(self):
        existing = self.manager.add_customer(
            "Existing Customer",
            "0000000018",
            "existing@example.invalid",
        )
        data_path = Path(self.manager.customers_file)
        previous_contents = data_path.read_bytes()

        with mock.patch("customer_lead.os.replace", side_effect=OSError("simulated")):
            with self.assertRaises(DataSaveError):
                self.manager.add_customer(
                    "Unwritten Customer",
                    "0000000019",
                    "unwritten@example.invalid",
                )

        self.assertEqual(list(self.manager.customers), [existing.customer_id])
        self.assertEqual(data_path.read_bytes(), previous_contents)
        self.assert_no_temporary_files()

    def test_failed_lead_saves_roll_back_registration_status_and_notes(self):
        lead = self.manager.add_lead(
            "Existing Lead", "0000000020", "existing-lead@example.invalid", "Website"
        )
        data_path = Path(self.manager.leads_file)
        previous_contents = data_path.read_bytes()

        with mock.patch("customer_lead.os.replace", side_effect=OSError("simulated")):
            with self.assertRaises(DataSaveError):
                self.manager.add_lead(
                    "Unwritten Lead", "0000000021", "unwritten-lead@example.invalid", "Other"
                )
        self.assertEqual(list(self.manager.leads), [lead.lead_id])
        self.assertEqual(data_path.read_bytes(), previous_contents)

        with mock.patch("customer_lead.os.replace", side_effect=OSError("simulated")):
            with self.assertRaises(DataSaveError):
                self.manager.update_lead_status(lead.lead_id, "Interested")
        self.assertEqual(lead.status, "New")
        self.assertEqual(data_path.read_bytes(), previous_contents)

        with mock.patch("customer_lead.os.replace", side_effect=OSError("simulated")):
            with self.assertRaises(DataSaveError):
                self.manager.add_interaction_note(
                    lead.lead_id, "Call", "This note must roll back"
                )
        self.assertEqual(lead.notes, [])
        self.assertEqual(data_path.read_bytes(), previous_contents)
        self.assert_no_temporary_files()

    def test_serialization_failure_preserves_file_and_cleans_temporary_file(self):
        self.manager.add_customer(
            "Serialization Customer",
            "0000000022",
            "serialization@example.invalid",
        )
        data_path = Path(self.manager.customers_file)
        previous_contents = data_path.read_bytes()

        with mock.patch("customer_lead.json.dump", side_effect=TypeError("simulated")):
            with self.assertRaises(DataSaveError):
                self.manager.save_customers()

        self.assertEqual(data_path.read_bytes(), previous_contents)
        self.assert_no_temporary_files()

    def test_malformed_json_raises_clear_error_without_echoing_contents(self):
        private_marker = "SYNTHETIC_PRIVATE_MARKER"
        Path("customers.txt").write_text(
            '{"record":"' + private_marker, encoding="utf-8"
        )

        with self.assertRaises(DataLoadError) as raised:
            CustomerLeadManager(data_dir=self.temp_dir.name)

        self.assertIn("Malformed JSON", str(raised.exception))
        self.assertNotIn(private_marker, str(raised.exception))

    def test_invalid_record_structures_are_rejected(self):
        valid_customer = {
            "customer_id": "CUST001",
            "name": "Synthetic Customer",
            "phone": "0000000023",
            "email": "synthetic@example.invalid",
            "category": "Regular",
        }
        valid_lead = {
            "lead_id": "LEAD001",
            "name": "Synthetic Lead",
            "phone": "0000000024",
            "email": "synthetic-lead@example.invalid",
            "source": "Website",
            "status": "New",
            "created_at": "2026-01-01 10:00",
        }
        lead_without_created_at = dict(valid_lead)
        del lead_without_created_at["created_at"]
        invalid_cases = (
            ("customers.txt", {"not": "an array"}),
            ("customers.txt", [valid_customer, "not an object"]),
            ("customers.txt", [{"customer_id": "CUST002"}]),
            ("leads.txt", [lead_without_created_at]),
            ("leads.txt", [dict(valid_lead, status="Unknown")]),
            ("leads.txt", [dict(valid_lead, notes="not an array")]),
            (
                "leads.txt",
                [dict(valid_lead, notes=[{"date": "2026-01-01"}])],
            ),
            ("leads.txt", [valid_lead, dict(valid_lead)]),
        )

        for filename, records in invalid_cases:
            with self.subTest(filename=filename, records=records):
                for data_filename in ("customers.txt", "leads.txt"):
                    Path(data_filename).unlink(missing_ok=True)
                Path(filename).write_text(json.dumps(records), encoding="utf-8")

                with self.assertRaises(DataLoadError):
                    CustomerLeadManager(data_dir=self.temp_dir.name)

    def test_loading_is_transactional_when_either_file_is_invalid(self):
        self.write_json(
            "customers.txt",
            [
                {
                    "customer_id": "CUST001",
                    "name": "Synthetic Customer",
                    "phone": "0000000025",
                    "email": "valid@example.invalid",
                }
            ],
        )
        Path("leads.txt").write_text("[{}]", encoding="utf-8")

        manager = CustomerLeadManager.__new__(CustomerLeadManager)
        original_customers = {"sentinel": object()}
        original_leads = {"sentinel": object()}
        manager.customers = original_customers
        manager.leads = original_leads
        manager.customers_file = str(Path(self.temp_dir.name) / "customers.txt")
        manager.leads_file = str(Path(self.temp_dir.name) / "leads.txt")
        with self.assertRaises(DataLoadError):
            manager.load_data()

        self.assertIs(manager.customers, original_customers)
        self.assertIs(manager.leads, original_leads)

    def test_default_paths_are_project_relative_without_loading_project_data(self):
        with mock.patch.object(CustomerLeadManager, "load_data", autospec=True) as load:
            manager = CustomerLeadManager()

        project_directory = Path(customer_lead.__file__).resolve().parent
        self.assertEqual(Path(manager.customers_file), project_directory / "customers.txt")
        self.assertEqual(Path(manager.leads_file), project_directory / "leads.txt")
        load.assert_called_once_with(manager)

    def test_explicit_data_directory_works_from_a_different_working_directory(self):
        other_directory = tempfile.TemporaryDirectory()
        self.addCleanup(other_directory.cleanup)
        original_cwd = Path.cwd()
        try:
            os.chdir(other_directory.name)
            manager = CustomerLeadManager(data_dir=self.temp_dir.name)
            manager.add_customer(
                "Path Customer", "0000000026", "path@example.invalid"
            )
        finally:
            os.chdir(original_cwd)

        self.assertTrue(Path(self.temp_dir.name, "customers.txt").is_file())
        self.assertFalse(Path(other_directory.name, "customers.txt").exists())

    def test_invalid_interaction_type_and_empty_description_are_rejected(self):
        lead = self.manager.add_lead(
            "Validation Lead", "0000000016", "validation@example.invalid", "Other"
        )

        with self.assertRaises(ValueError):
            self.manager.add_interaction_note(lead.lead_id, "Text", "Description")
        with self.assertRaises(ValueError):
            self.manager.add_interaction_note(lead.lead_id, "Call", "  ")

        self.assertEqual(lead.notes, [])

    def test_follow_up_date_is_validated_and_persisted_as_iso(self):
        lead = self.manager.add_lead(
            "Follow-up Lead", "0000000027", "followup@example.invalid", "Website"
        )
        self.manager.add_interaction_note(
            lead.lead_id, "Call", "Existing interaction history"
        )
        previous_notes = list(lead.notes)
        previous_status = lead.status

        updated = self.manager.set_lead_follow_up(
            lead.lead_id, date(2026, 6, 15)
        )
        records = json.loads(Path("leads.txt").read_text(encoding="utf-8"))
        reloaded_manager = CustomerLeadManager(data_dir=self.temp_dir.name)

        self.assertIs(updated, lead)
        self.assertEqual(lead.follow_up_date, "2026-06-15")
        self.assertEqual(records[0]["follow_up_date"], "2026-06-15")
        self.assertEqual(
            reloaded_manager.leads[lead.lead_id].follow_up_date, "2026-06-15"
        )
        self.assertEqual(lead.status, previous_status)
        self.assertEqual(lead.notes, previous_notes)

    def test_follow_up_date_rejects_blank_malformed_and_impossible_values(self):
        lead = self.manager.add_lead(
            "Date Validation Lead",
            "0000000028",
            "date-validation@example.invalid",
            "Website",
        )
        invalid_dates = (
            "",
            "   ",
            "2026-6-15",
            "20260615",
            "2026-02-30",
            datetime(2026, 6, 15),
            20260615,
        )

        for invalid_date in invalid_dates:
            with self.subTest(invalid_date=invalid_date):
                with self.assertRaises(ValueError):
                    self.manager.set_lead_follow_up(lead.lead_id, invalid_date)

        self.assertIsNone(lead.follow_up_date)

    def test_clearing_follow_up_only_removes_date_and_summary_entries(self):
        lead = self.manager.add_lead(
            "Clear Follow-up Lead",
            "0000000029",
            "clear-followup@example.invalid",
            "Referral",
        )
        self.manager.update_lead_status(lead.lead_id, "Interested")
        self.manager.add_interaction_note(
            lead.lead_id, "Email", "Keep this interaction history"
        )
        original_status = lead.status
        original_notes = list(lead.notes)
        self.manager.set_lead_follow_up(lead.lead_id, "2026-06-16")

        self.manager.set_lead_follow_up(lead.lead_id, None)

        self.assertIsNone(lead.follow_up_date)
        self.assertEqual(lead.status, original_status)
        self.assertEqual(lead.notes, original_notes)
        self.assertEqual(self.manager.get_upcoming_follow_ups(date(2026, 6, 15)), [])
        self.assertEqual(self.manager.get_overdue_follow_ups(date(2026, 6, 15)), [])

    def test_failed_follow_up_save_rolls_back_memory_and_preserves_file(self):
        lead = self.manager.add_lead(
            "Rollback Follow-up Lead",
            "0000000030",
            "rollback-followup@example.invalid",
            "Website",
        )
        self.manager.set_lead_follow_up(lead.lead_id, "2026-06-17")
        data_path = Path(self.manager.leads_file)
        previous_contents = data_path.read_bytes()

        with mock.patch("customer_lead.os.replace", side_effect=OSError("simulated")):
            with self.assertRaises(DataSaveError):
                self.manager.set_lead_follow_up(lead.lead_id, "2026-06-18")

        self.assertEqual(lead.follow_up_date, "2026-06-17")
        self.assertEqual(data_path.read_bytes(), previous_contents)
        self.assert_no_temporary_files()

    def test_follow_up_summaries_apply_boundaries_status_and_sort_order(self):
        today = date(2026, 5, 10)
        lead_specs = (
            ("Overdue A", "0000000031", "2026-05-09", "New"),
            ("Overdue B", "0000000032", "2026-05-09", "Contacted"),
            ("Due Today", "0000000033", "2026-05-10", "New"),
            ("Horizon", "0000000034", "2026-05-17", "Interested"),
            ("Beyond Horizon", "0000000035", "2026-05-18", "New"),
            ("No Date", "0000000036", None, "New"),
            ("Converted", "0000000037", "2026-05-11", "Converted"),
            ("Lost", "0000000038", "2026-05-09", "Lost"),
        )

        for index, (name, phone, follow_up, status) in enumerate(lead_specs):
            lead = self.manager.add_lead(
                name,
                phone,
                f"followup-{index}@example.invalid",
                "Website",
            )
            if status == "Converted":
                # Simulate a historical record: users cannot set this status.
                lead.status = "Converted"
                self.manager.save_leads()
            elif status != "New":
                self.manager.update_lead_status(lead.lead_id, status)
            if follow_up is not None:
                self.manager.set_lead_follow_up(lead.lead_id, follow_up)

        upcoming = self.manager.get_upcoming_follow_ups(today=today)
        overdue = self.manager.get_overdue_follow_ups(today=today)

        self.assertEqual(
            [lead.lead_id for lead in upcoming],
            ["LEAD003", "LEAD004"],
        )
        self.assertEqual(
            [lead.lead_id for lead in overdue],
            ["LEAD001", "LEAD002"],
        )

    def test_invalid_persisted_follow_up_date_is_rejected(self):
        self.write_json(
            "leads.txt",
            [
                {
                    "lead_id": "LEAD009",
                    "name": "Synthetic Lead",
                    "phone": "0000000039",
                    "email": "stored-date@example.invalid",
                    "source": "Website",
                    "status": "New",
                    "created_at": "2026-01-01 10:00",
                    "follow_up_date": "2026-02-30",
                }
            ],
        )

        with self.assertRaises(DataLoadError) as raised:
            CustomerLeadManager(data_dir=self.temp_dir.name)

        self.assertIn("Invalid follow-up date", str(raised.exception))
        self.assertNotIn("2026-02-30", str(raised.exception))

    def test_legacy_records_without_conversion_links_load_unchanged(self):
        self.write_json(
            "customers.txt",
            [
                {
                    "customer_id": "CUST001",
                    "name": "Legacy Customer",
                    "phone": "0000000040",
                    "email": "legacy-customer@example.invalid",
                    "category": "Premium",
                }
            ],
        )
        self.write_json(
            "leads.txt",
            [
                {
                    "lead_id": "LEAD001",
                    "name": "Legacy Lead",
                    "phone": "0000000041",
                    "email": "legacy-lead@example.invalid",
                    "source": "Website",
                    "status": "New",
                    "created_at": "2026-01-01 10:00",
                }
            ],
        )

        manager = CustomerLeadManager(data_dir=self.temp_dir.name)

        self.assertIsNone(manager.customers["CUST001"].source_lead_id)
        self.assertIsNone(manager.leads["LEAD001"].converted_customer_id)

    def test_legacy_linked_converted_records_load_save_and_reload(self):
        note = {
            "date": "2026-01-02",
            "interaction_type": "Call",
            "description": "Synthetic legacy note",
        }
        self.write_json(
            "customers.txt",
            [
                {
                    "customer_id": "CUST001",
                    "name": "Synthetic Customer",
                    "phone": "0000000040",
                    "email": "legacy-customer@example.invalid",
                    "category": "Regular",
                    "source_lead_id": "LEAD001",
                }
            ],
        )
        self.write_json(
            "leads.txt",
            [
                {
                    "lead_id": "LEAD001",
                    "name": "Synthetic Lead",
                    "phone": "0000000041",
                    "email": "legacy-lead@example.invalid",
                    "source": "Website",
                    "status": "Converted",
                    "created_at": "2026-01-01 10:00",
                    "notes": [note],
                    "follow_up_date": "2026-01-15",
                    "converted_customer_id": "CUST001",
                }
            ],
        )

        manager = CustomerLeadManager(data_dir=self.temp_dir.name)
        manager.save_customers()
        manager.save_leads()
        reloaded = CustomerLeadManager(data_dir=self.temp_dir.name)

        self.assertEqual(reloaded.leads["LEAD001"].status, "Converted")
        self.assertEqual(reloaded.customers["CUST001"].source_lead_id, "LEAD001")
        self.assertEqual(reloaded.leads["LEAD001"].converted_customer_id, "CUST001")
        self.assertEqual(reloaded.leads["LEAD001"].notes, [note])
        self.assertEqual(reloaded.leads["LEAD001"].follow_up_date, "2026-01-15")

    def test_mismatched_legacy_customer_lead_links_are_rejected(self):
        self.write_json(
            "customers.txt",
            [
                {
                    "customer_id": "CUST001",
                    "name": "Synthetic Customer",
                    "phone": "0000000052",
                    "email": "linked@example.invalid",
                    "category": "Regular",
                    "source_lead_id": "LEAD001",
                }
            ],
        )
        self.write_json(
            "leads.txt",
            [
                {
                    "lead_id": "LEAD001",
                    "name": "Synthetic Lead",
                    "phone": "0000000053",
                    "email": "linked-lead@example.invalid",
                    "source": "Website",
                    "status": "Converted",
                    "created_at": "2026-01-01 10:00",
                    "converted_customer_id": "CUST999",
                }
            ],
        )

        with self.assertRaises(DataLoadError):
            CustomerLeadManager(data_dir=self.temp_dir.name)


if __name__ == "__main__":
    unittest.main()
