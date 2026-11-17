"""Streamlit AppTests use copied source and isolated synthetic TXT data."""

from datetime import date, timedelta
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MISSING = object()


class CustomerLeadAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="clms-app-test-")
        self.addCleanup(self.temp_dir.cleanup)
        self.app_dir = Path(self.temp_dir.name)
        for name in ("customer_lead.py", "customer_lead_system.py"):
            shutil.copy2(PROJECT_ROOT / name, self.app_dir / name)
        self.app_path = self.app_dir / "customer_lead_system.py"

    def run_app(self, app):
        previous = sys.modules.pop("customer_lead", _MISSING)
        try:
            app.run()
        finally:
            sys.modules.pop("customer_lead", None)
            if previous is not _MISSING:
                sys.modules["customer_lead"] = previous

    def new_app(self):
        app = AppTest.from_file(str(self.app_path), default_timeout=30)
        self.run_app(app)
        self.assertFalse(app.exception)
        manager = app.session_state["manager"]
        self.assertEqual(manager.data_file.parent, self.app_dir)
        return app

    def go(self, app, page):
        app.radio[0].set_value(page)
        self.run_app(app)
        self.assertFalse(app.exception)

    @staticmethod
    def submit(app, key):
        app.form_submit_button(key=key).click()

    def test_navigation_dashboard_counts_and_empty_states(self):
        app = self.new_app()
        pages = ["Dashboard", "Customers", "Leads", "Follow-ups & Notes"]
        self.assertEqual(list(app.radio[0].options), pages)
        self.assertEqual({metric.label: metric.value for metric in app.metric},
                         {"Total customers": "0", "Total leads": "0"})
        for page in pages:
            self.go(app, page)
            self.assertEqual(app.header[0].value, page)
        self.go(app, "Customers")
        self.assertTrue(any("No customers yet" in item.value for item in app.info))
        self.go(app, "Leads")
        self.assertTrue(any("No leads yet" in item.value for item in app.info))
        app.session_state["manager"].add_lead(
            "Empty activity lead", "3400000001", "emptyactivity@example.invalid", "Website"
        )
        self.go(app, "Follow-ups & Notes")
        self.assertTrue(any("No interaction notes" in item.value for item in app.info))

    def test_dashboard_counts_synthetic_populated_records(self):
        app = self.new_app()
        manager = app.session_state["manager"]
        manager.add_customer("Dashboard Customer", "3100000001", "dashcust@example.invalid")
        statuses = ("New", "Contacted", "Interested", "Lost")
        for index, status in enumerate(statuses, start=1):
            lead = manager.add_lead(f"Dashboard Lead {index}", f"320000000{index}",
                                    f"dash{index}@example.invalid", "Website")
            manager.update_lead_status(lead.lead_id, status)
        converted = manager.add_lead("Dashboard Converted", "3200000005",
                                     "dash5@example.invalid", "Referral")
        manager.convert_lead(converted.lead_id)
        self.run_app(app)
        self.assertEqual({item.label: item.value for item in app.metric},
                         {"Total customers": "2", "Total leads": "5"})
        counts = list(app.dataframe[0].value["Leads"])
        self.assertEqual(counts, [1, 1, 1, 1, 1])

    def test_customer_add_search_edit_segment_and_delete(self):
        app = self.new_app()
        self.go(app, "Customers")
        app.text_input(key="customer_name").set_value("Synthetic Customer")
        app.text_input(key="customer_phone").set_value("3100000001")
        app.text_input(key="customer_email").set_value("synthetic@example.invalid")
        self.submit(app, "submit_add_customer")
        self.run_app(app)
        self.assertTrue(any("Customer added" in x.value for x in app.success))
        manager = app.session_state["manager"]
        customer_id = next(iter(manager.customers))
        app.text_input(key="customer_search").set_value("synthetic@example.invalid")
        self.run_app(app)
        self.assertEqual(len(app.dataframe), 1)
        self.assertNotIn("Phone", app.dataframe[0].value.columns)
        app.text_input(key="customer_search").set_value("no matching customer")
        self.run_app(app)
        self.assertTrue(any("No customers match" in x.value for x in app.info))
        app.text_input(key="customer_search").set_value("synthetic@example.invalid")
        self.run_app(app)
        app.selectbox(key="customer_selected_id").select(customer_id)
        app.selectbox(key="edit_customer_segment").select("Premium")
        app.text_input(key="edit_customer_name").set_value("Updated Customer")
        self.submit(app, "submit_edit_customer")
        self.run_app(app)
        self.assertEqual(manager.customers[customer_id].name, "Updated Customer")
        app.checkbox(key="confirm_delete_customer").set_value(True)
        self.run_app(app)
        app.button(key="delete_customer").click()
        self.run_app(app)
        self.assertEqual(manager.customers, {})

    def test_lead_add_filter_status_update_and_conversion(self):
        app = self.new_app()
        self.go(app, "Leads")
        app.text_input(key="lead_name").set_value("Synthetic Lead")
        app.text_input(key="lead_phone").set_value("3200000001")
        app.text_input(key="lead_email").set_value("syntheticlead@example.invalid")
        app.text_input(key="new_lead_source").set_value("Referral")
        self.submit(app, "submit_add_lead")
        self.run_app(app)
        manager = app.session_state["manager"]
        lead_id = next(iter(manager.leads))
        self.assertTrue(any("Lead added" in x.value for x in app.success))
        app.text_input(key="lead_search").set_value("Referral")
        self.run_app(app)
        self.assertEqual(list(app.dataframe[0].value["ID"]), [lead_id])
        app.selectbox(key="lead_source_filter").select("Referral")
        self.run_app(app)
        self.assertEqual(list(app.dataframe[0].value["ID"]), [lead_id])
        app.selectbox(key="lead_source_filter").select("All sources")
        self.run_app(app)
        app.selectbox(key="new_lead_status").select("Interested")
        self.submit(app, "submit_status")
        self.run_app(app)
        self.assertEqual(manager.leads[lead_id].status, "Interested")
        self.assertTrue(any("status updated" in x.value.lower() for x in app.success))
        app.selectbox(key="conversion_segment").select("Business")
        app.button(key="convert_lead").click()
        self.run_app(app)
        self.assertEqual(manager.leads[lead_id].status, "Converted")
        self.assertEqual(len(manager.customers), 1)
        self.assertTrue(any("Lead converted" in x.value for x in app.success))

    def test_follow_up_notes_completion_and_feedback(self):
        app = self.new_app()
        manager = app.session_state["manager"]
        lead = manager.add_lead("Synthetic Follow-up", "3300000001",
                                "followup@example.invalid", "Website")
        self.go(app, "Follow-ups & Notes")
        option = next(value for value in app.selectbox(key="activity_owner").options
                      if lead.lead_id in value)
        app.selectbox(key="activity_owner").select(option)
        self.run_app(app)
        due = date.today() + timedelta(days=1)
        app.date_input(key="new_follow_up_date").set_value(due)
        app.text_input(key="new_follow_up_description").set_value("Call synthetic lead")
        self.submit(app, "submit_add_follow_up")
        self.run_app(app)
        self.assertTrue(any("Follow-up added" in x.value for x in app.success))
        self.assertEqual(len(lead.follow_ups), 1)
        follow_up_id = lead.follow_ups[0]["follow_up_id"]
        changed_due = due + timedelta(days=2)
        app.date_input(key="edit_follow_up_date").set_value(changed_due)
        app.text_input(key="edit_follow_up_description").set_value("Updated synthetic call")
        self.submit(app, "submit_edit_follow_up")
        self.run_app(app)
        self.assertEqual(lead.follow_ups[0]["date"], changed_due.isoformat())
        self.assertEqual(lead.follow_ups[0]["description"], "Updated synthetic call")
        app.text_area(key="new_note_description").set_value("Synthetic interaction note")
        self.submit(app, "submit_add_note")
        self.run_app(app)
        self.assertEqual(lead.notes[0]["description"], "Synthetic interaction note")
        self.assertTrue(any("Interaction note added" in x.value for x in app.success))
        app.button(key="toggle_follow_up").click()
        self.run_app(app)
        self.assertTrue(lead.follow_ups[0]["completed"])
        self.assertTrue(any("Follow-up status updated" in x.value for x in app.success))
        self.assertEqual(follow_up_id, lead.follow_ups[0]["follow_up_id"])

    def test_validation_error_is_safe_and_does_not_expose_paths(self):
        app = self.new_app()
        self.go(app, "Customers")
        self.submit(app, "submit_add_customer")
        self.run_app(app)
        self.assertTrue(any("Name cannot be empty" in x.value for x in app.error))
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
