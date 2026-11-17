"""Streamlit AppTests using an isolated copy and synthetic records."""

from datetime import date, timedelta
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MISSING = object()


class CustomerLeadSystemAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="crm-app-test-")
        self.addCleanup(self.temp_dir.cleanup)
        self.app_dir = Path(self.temp_dir.name)
        for filename in ("customer_lead.py", "customer_lead_system.py"):
            shutil.copy2(PROJECT_ROOT / filename, self.app_dir)
        self.app_path = self.app_dir / "customer_lead_system.py"

    def _run(self, app):
        previous_module = sys.modules.pop("customer_lead", _MISSING)
        try:
            app.run()
        finally:
            sys.modules.pop("customer_lead", None)
            if previous_module is not _MISSING:
                sys.modules["customer_lead"] = previous_module

    def _new_app(self):
        app = AppTest.from_file(str(self.app_path), default_timeout=30)
        self._run(app)
        manager = app.session_state["manager"]
        self.assertEqual(Path(manager.customers_file).parent, self.app_dir)
        self.assertEqual(Path(manager.leads_file).parent, self.app_dir)
        self.assertFalse(app.exception)
        return app

    def _go(self, app, page):
        app.radio[0].set_value(page)
        self._run(app)
        self.assertFalse(app.exception, f"Unexpected app exception on {page}.")

    def _write_records(self, filename, records):
        (self.app_dir / filename).write_text(
            json.dumps(records, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _customer_record(customer_id, name="Synthetic Customer"):
        return {
            "customer_id": customer_id,
            "name": name,
            "phone": "0000001001",
            "email": f"{customer_id.lower()}@example.invalid",
            "category": "Regular",
        }

    @staticmethod
    def _lead_record(
        lead_id,
        name="Synthetic Lead",
        status="New",
        follow_up=None,
        notes=None,
    ):
        return {
            "lead_id": lead_id,
            "name": name,
            "phone": "0000002001",
            "email": f"{lead_id.lower()}@example.invalid",
            "source": "Website",
            "status": status,
            "created_at": "2026-01-01 10:00",
            "notes": notes or [],
            "follow_up_date": follow_up,
        }

    def test_navigation_and_empty_states_on_all_four_pages(self):
        app = self._new_app()
        pages = ["Dashboard", "Customers", "Leads", "Follow-ups & Notes"]
        self.assertEqual(list(app.radio[0].options), pages)

        for page in pages:
            self._go(app, page)
            self.assertEqual(app.header[0].value, page)

        self._go(app, "Customers")
        self.assertTrue(any("No customers yet" in item.value for item in app.info))
        self._go(app, "Leads")
        self.assertTrue(any("No leads yet" in item.value for item in app.info))
        self._go(app, "Follow-ups & Notes")
        self.assertTrue(any("No overdue follow-ups" in item.value for item in app.info))
        self.assertTrue(any("No upcoming follow-ups" in item.value for item in app.info))

    def test_dashboard_counts_empty_and_populated_records(self):
        app = self._new_app()
        metrics = {metric.label: metric.value for metric in app.metric}
        self.assertEqual(metrics["Total customers"], "0")
        self.assertEqual(metrics["Total leads"], "0")
        self.assertEqual(len(app.dataframe), 1)
        self.assertEqual(list(app.dataframe[0].value["Leads"]), [0, 0, 0, 0, 0])

        self._write_records(
            "customers.txt",
            [self._customer_record("CUST001"), self._customer_record("CUST002")],
        )
        statuses = ["New", "Contacted", "Interested", "Converted", "Lost"]
        self._write_records(
            "leads.txt",
            [
                self._lead_record(f"LEAD00{index}", status=status)
                for index, status in enumerate(statuses, start=1)
            ],
        )
        app = self._new_app()
        metrics = {metric.label: metric.value for metric in app.metric}
        self.assertEqual(metrics["Total customers"], "2")
        self.assertEqual(metrics["Total leads"], "5")
        self.assertEqual(list(app.dataframe[0].value["Leads"]), [1, 1, 1, 1, 1])

    def test_customer_registration_search_and_selected_details(self):
        app = self._new_app()
        self._go(app, "Customers")
        app.text_input(key="customer_name").set_value("Synthetic UI Customer")
        app.text_input(key="customer_phone").set_value("0000001234")
        app.text_input(key="customer_email").set_value("customer@example.invalid")
        app.form_submit_button[0].click()
        self._run(app)
        self.assertTrue(any("Customer registered" in item.value for item in app.success))

        manager = app.session_state["manager"]
        customer_id = next(iter(manager.customers))
        self.assertTrue(customer_id.startswith("CUST"))
        self.assertEqual(len(app.dataframe), 1)
        self.assertNotIn("Phone", app.dataframe[0].value.columns)
        self.assertNotIn("Email", app.dataframe[0].value.columns)

        app.text_input(key="customer_search").set_value("0000001234")
        self._run(app)
        self.assertEqual(list(app.dataframe[0].value["Customer ID"]), [customer_id])
        app.selectbox(key="customer_selected_id").select(customer_id)
        self._run(app)
        self.assertTrue(any("Synthetic UI Customer" in item.value for item in app.markdown))
        self.assertTrue(any("customer@example.invalid" in item.value for item in app.markdown))

    def test_lead_registration_search_filter_and_status_update(self):
        app = self._new_app()
        self._go(app, "Leads")
        app.text_input(key="lead_name").set_value("Synthetic UI Lead")
        app.text_input(key="lead_phone").set_value("0000002345")
        app.text_input(key="lead_email").set_value("lead@example.invalid")
        app.form_submit_button[0].click()
        self._run(app)
        self.assertTrue(any("Lead registered" in item.value for item in app.success))

        manager = app.session_state["manager"]
        lead_id = next(iter(manager.leads))
        self.assertEqual(manager.leads[lead_id].status, "New")
        app.text_input(key="lead_search").set_value("Synthetic UI Lead")
        self._run(app)
        self.assertEqual(list(app.dataframe[0].value["Lead ID"]), [lead_id])

        app.selectbox(key="lead_new_status").select("Interested")
        app.form_submit_button[1].click()
        self._run(app)
        self.assertEqual(manager.leads[lead_id].status, "Interested")
        self.assertTrue(any("Lead status updated" in item.value for item in app.success))

        app.selectbox(key="lead_status_filter").select("Lost")
        self._run(app)
        self.assertTrue(
            any("No leads match" in item.value for item in app.info)
        )

    def test_historical_converted_lead_is_visible_without_conversion_control(self):
        customer = self._customer_record("CUST001")
        customer["source_lead_id"] = "LEAD001"
        lead = self._lead_record("LEAD001", status="Converted")
        lead["converted_customer_id"] = "CUST001"
        self._write_records("customers.txt", [customer])
        self._write_records("leads.txt", [lead])

        app = self._new_app()
        self._go(app, "Leads")
        self.assertEqual(list(app.dataframe[0].value["Status"]), ["Converted"])
        self.assertFalse(any("Convert" in button.label for button in app.button))

    def test_follow_up_queues_update_and_clear(self):
        today = date.today()
        self._write_records(
            "leads.txt",
            [
                self._lead_record(
                    "LEAD001",
                    "Overdue synthetic",
                    follow_up=(today - timedelta(days=1)).isoformat(),
                ),
                self._lead_record(
                    "LEAD002",
                    "Upcoming synthetic",
                    follow_up=(today + timedelta(days=2)).isoformat(),
                ),
            ],
        )
        app = self._new_app()
        self._go(app, "Follow-ups & Notes")
        self.assertEqual(len(app.dataframe), 2)
        self.assertEqual(list(app.dataframe[0].value["Lead ID"]), ["LEAD001"])
        self.assertEqual(list(app.dataframe[1].value["Lead ID"]), ["LEAD002"])

        app.selectbox(key="activity_lead_id").select("LEAD002")
        self._run(app)
        chosen_date = today + timedelta(days=3)
        app.date_input[0].set_value(chosen_date)
        app.form_submit_button[0].click()
        self._run(app)
        manager = app.session_state["manager"]
        self.assertEqual(manager.leads["LEAD002"].follow_up_date, chosen_date.isoformat())
        self.assertTrue(any("Follow-up date saved" in item.value for item in app.success))

        app.checkbox[0].set_value(True)
        app.form_submit_button[0].click()
        self._run(app)
        self.assertIsNone(manager.leads["LEAD002"].follow_up_date)
        self.assertTrue(any("Follow-up date cleared" in item.value for item in app.success))

    def test_interaction_notes_are_chronological_and_new_note_is_shown(self):
        self._write_records(
            "leads.txt",
            [
                self._lead_record(
                    "LEAD001",
                    notes=[
                        {"date": "2026-02-02 10:00", "interaction_type": "Email", "description": "Later synthetic note"},
                        {"date": "2026-01-02 10:00", "interaction_type": "Call", "description": "Earlier synthetic note"},
                    ],
                )
            ],
        )
        app = self._new_app()
        self._go(app, "Follow-ups & Notes")
        markdown = [item.value for item in app.markdown]
        self.assertLess(
            next(i for i, value in enumerate(markdown) if "2026-01-02" in value),
            next(i for i, value in enumerate(markdown) if "2026-02-02" in value),
        )
        self.assertTrue(any("Latest interaction" in item.value for item in app.caption))

        app.text_area(key="interaction_description").set_value("New synthetic note")
        app.form_submit_button[1].click()
        self._run(app)
        manager = app.session_state["manager"]
        self.assertEqual(len(manager.leads["LEAD001"].notes), 3)
        self.assertTrue(any("Interaction note added" in item.value for item in app.success))
        self.assertTrue(any("New synthetic note" in item.value for item in app.markdown))

    def test_invalid_input_and_failed_save_show_safe_errors(self):
        app = self._new_app()
        self._go(app, "Customers")
        app.form_submit_button[0].click()
        self._run(app)
        self.assertTrue(any("Name cannot be empty" in item.value for item in app.error))
        self.assertFalse(app.exception)

        manager = app.session_state["manager"]
        manager.add_customer = mock.Mock(side_effect=OSError("private path detail"))
        app.text_input(key="customer_name").set_value("Synthetic Failure")
        app.text_input(key="customer_phone").set_value("0000003456")
        app.text_input(key="customer_email").set_value("failure@example.invalid")
        app.form_submit_button[0].click()
        self._run(app)
        errors = [item.value for item in app.error]
        self.assertTrue(any("could not be saved" in value for value in errors))
        self.assertFalse(any("private path detail" in value for value in errors))
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
