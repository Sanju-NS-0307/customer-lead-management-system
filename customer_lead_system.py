"""Simple four-page Streamlit interface for customer and lead records."""

from datetime import date

import streamlit as st

from customer_lead import CustomerLeadManager, SEGMENTS, STATUSES, INTERACTION_TYPES


st.set_page_config(page_title="Customer and Lead Management", layout="wide")
if "manager" not in st.session_state:
    st.session_state.manager = CustomerLeadManager()
manager = st.session_state.manager


def finish_action(message):
    st.session_state["message"] = message
    st.rerun()


def show_message():
    message = st.session_state.pop("message", None)
    if message:
        st.success(message)


def show_error(action, error):
    if isinstance(error, ValueError):
        st.error(f"{action} was not completed: {error}")
    else:
        st.error(f"{action} could not be saved. Check local storage and try again.")


def run_action(action, success_message):
    try:
        action()
    except Exception as error:
        show_error("This action", error)
    else:
        finish_action(success_message)


def registration_form(record_type):
    is_customer = record_type == "customer"
    label = "customer" if is_customer else "lead"
    with st.form(f"add_{label}"):
        name = st.text_input("Full name", key=f"{label}_name")
        phone = st.text_input("10-digit phone", key=f"{label}_phone")
        email = st.text_input("Email address", key=f"{label}_email")
        if is_customer:
            category = st.selectbox("Segment", SEGMENTS, key="new_customer_segment")
            submitted = st.form_submit_button("Add customer", key="submit_add_customer")
        else:
            source = st.text_input("Lead source", key="new_lead_source")
            submitted = st.form_submit_button("Add lead", key="submit_add_lead")
    if submitted:
        try:
            if is_customer:
                record = manager.add_customer(name, phone, email, category)
                message = f"Customer added. ID: {record.customer_id}"
            else:
                record = manager.add_lead(name, phone, email, source)
                message = f"Lead added. ID: {record.lead_id}"
        except Exception as error:
            show_error(f"Adding {label}", error)
        else:
            finish_action(message)


def render_dashboard():
    st.header("Dashboard")
    left, right = st.columns(2)
    left.metric("Total customers", len(manager.customers))
    right.metric("Total leads", len(manager.leads))
    st.subheader("Lead status")
    st.dataframe([{"Status": status,
                   "Leads": sum(lead.status == status for lead in manager.leads.values())}
                  for status in STATUSES], hide_index=True, width="stretch")
    summary = manager.get_follow_up_summary()
    st.subheader("Follow-ups")
    st.write(f"Overdue: **{len(summary['overdue'])}** · Due today: **{len(summary['today'])}** · Upcoming: **{len(summary['upcoming'])}**")


def render_customers():
    st.header("Customers")
    with st.expander("Add a customer", expanded=not manager.customers):
        registration_form("customer")
    if not manager.customers:
        st.info("No customers yet. Add a customer above to get started.")
        return

    search, segment = st.columns(2)
    query = search.text_input("Search name, phone, email, or ID", key="customer_search")
    chosen_segment = segment.selectbox("Segment", ["All segments", *SEGMENTS], key="customer_segment_filter")
    customers = manager.search_customers(query, chosen_segment)
    if not customers:
        st.info("No customers match these filters.")
        return
    st.dataframe([{"ID": item.customer_id, "Name": item.name,
                    "Segment": item.category} for item in customers],
                 hide_index=True, width="stretch")
    customer_id = st.selectbox("Select a customer", [item.customer_id for item in customers],
                               key="customer_selected_id")
    customer = manager.customers[customer_id]
    with st.expander("Customer details and actions", expanded=True):
        st.write(customer.display_details())
        with st.form("edit_customer"):
            name = st.text_input("Name", value=customer.name, key="edit_customer_name")
            phone = st.text_input("Phone", value=customer.phone, key="edit_customer_phone")
            email = st.text_input("Email", value=customer.email, key="edit_customer_email")
            category = st.selectbox("Segment", SEGMENTS, index=SEGMENTS.index(customer.category), key="edit_customer_segment")
            save = st.form_submit_button("Save customer changes", key="submit_edit_customer")
        if save:
            try:
                manager.edit_customer(customer_id, name, phone, email, category)
            except Exception as error:
                show_error("Customer update", error)
            else:
                finish_action("Customer updated.")
        confirm = st.checkbox("Confirm customer deletion", key="confirm_delete_customer")
        if st.button("Delete customer", disabled=not confirm, key="delete_customer"):
            run_action(lambda: manager.delete_customer(customer_id), "Customer deleted.")


def render_leads():
    st.header("Leads")
    with st.expander("Add a lead", expanded=not manager.leads):
        registration_form("lead")
    if not manager.leads:
        st.info("No leads yet. Add a lead above to get started.")
        return

    search, status_filter, source_filter = st.columns(3)
    query = search.text_input("Search name, phone, email, source, or ID", key="lead_search")
    status = status_filter.selectbox("Status", ["All statuses", *STATUSES], key="lead_status_filter")
    sources = sorted({lead.source for lead in manager.leads.values()})
    source = source_filter.selectbox("Source", ["All sources", *sources], key="lead_source_filter")
    leads = manager.search_leads(query, status, source)
    if not leads:
        st.info("No leads match these filters.")
        return
    st.dataframe([{"ID": lead.lead_id, "Name": lead.name, "Source": lead.source,
                    "Status": lead.status} for lead in leads], hide_index=True, width="stretch")
    lead_id = st.selectbox("Select a lead", [lead.lead_id for lead in leads], key="lead_selected_id")
    lead = manager.leads[lead_id]
    with st.expander("Lead details and actions", expanded=True):
        st.write(lead.display_details())
        if lead.status != "Converted":
            with st.form("edit_lead"):
                name = st.text_input("Name", value=lead.name, key="edit_lead_name")
                phone = st.text_input("Phone", value=lead.phone, key="edit_lead_phone")
                email = st.text_input("Email", value=lead.email, key="edit_lead_email")
                source = st.text_input("Source", value=lead.source, key="edit_lead_source")
                edit = st.form_submit_button("Save lead changes", key="submit_edit_lead")
            if edit:
                try:
                    manager.edit_lead(lead_id, name, phone, email, source)
                except Exception as error:
                    show_error("Lead update", error)
                else:
                    finish_action("Lead updated.")
            with st.form("update_lead_status"):
                choices = [item for item in STATUSES if item != "Converted"]
                new_status = st.selectbox("Update status", choices,
                                          index=choices.index(lead.status), key="new_lead_status")
                update = st.form_submit_button("Save status", key="submit_status")
            if update:
                try:
                    manager.update_lead_status(lead_id, new_status)
                except Exception as error:
                    show_error("Status update", error)
                else:
                    finish_action("Lead status updated.")
            if lead.status in ("New", "Contacted", "Interested"):
                category = st.selectbox("New customer segment", SEGMENTS, key="conversion_segment")
                if st.button("Convert lead to customer", key="convert_lead"):
                    try:
                        customer = manager.convert_lead(lead_id, category)
                    except Exception as error:
                        show_error("Lead conversion", error)
                    else:
                        finish_action(f"Lead converted. Customer ID: {customer.customer_id}")
            confirm = st.checkbox("Confirm lead deletion", key="confirm_delete_lead")
            if st.button("Delete lead", disabled=not confirm, key="delete_lead"):
                run_action(lambda: manager.delete_lead(lead_id), "Lead deleted.")
        else:
            customer_id = lead.converted_customer_id
            st.info(f"Converted to customer: {customer_id}")


def render_follow_ups_and_notes():
    st.header("Follow-ups & Notes")
    summary = manager.get_follow_up_summary()
    for label, key in (("Overdue", "overdue"), ("Due today", "today"),
                       ("Upcoming", "upcoming"), ("Completed", "completed")):
        st.subheader(f"{label} follow-ups")
        items = summary[key]
        if items:
            st.dataframe([{"Date": item["date"], "ID": item["owner_id"],
                            "Name": item["name"], "Status": item["status"],
                            "Description": item["description"]} for item in items],
                         hide_index=True, width="stretch")
        else:
            st.caption(f"No {label.lower()} follow-ups.")

    entities = [("Customer", key, item.name) for key, item in manager.customers.items()]
    entities += [("Lead", key, item.name) for key, item in manager.leads.items()]
    if not entities:
        st.info("Add a customer or lead to schedule follow-ups and record notes.")
        return
    options = {f"{kind}: {record_id} — {name}": (kind.lower(), record_id)
               for kind, record_id, name in entities}
    selected = st.selectbox("Select a customer or lead", list(options), key="activity_owner")
    owner_type, owner_id = options[selected]
    owner = manager.customers[owner_id] if owner_type == "customer" else manager.leads[owner_id]

    st.subheader("Schedule a follow-up")
    with st.form("add_follow_up"):
        due_date = st.date_input("Due date", value=date.today(), key="new_follow_up_date")
        description = st.text_input("What needs to happen?", key="new_follow_up_description")
        submitted = st.form_submit_button("Add follow-up", key="submit_add_follow_up")
    if submitted:
        try:
            manager.add_follow_up(owner_type, owner_id, due_date.isoformat(), description)
        except Exception as error:
            show_error("Follow-up", error)
        else:
            finish_action("Follow-up added.")

    st.subheader("Update or complete a follow-up")
    if owner.follow_ups:
        follow_up_id = st.selectbox("Follow-up", [item["follow_up_id"] for item in owner.follow_ups], key="selected_follow_up")
        item = next(row for row in owner.follow_ups if row["follow_up_id"] == follow_up_id)
        with st.form("edit_follow_up"):
            changed_date = st.date_input("Due date", value=date.fromisoformat(item["date"]), key="edit_follow_up_date")
            changed_description = st.text_input("Description", value=item["description"], key="edit_follow_up_description")
            changed = st.form_submit_button("Save follow-up", key="submit_edit_follow_up")
        if changed:
            try:
                manager.update_follow_up(follow_up_id, changed_date.isoformat(), changed_description)
            except Exception as error:
                show_error("Follow-up update", error)
            else:
                finish_action("Follow-up updated.")
        if st.button("Mark follow-up complete" if not item["completed"] else "Reopen follow-up", key="toggle_follow_up"):
            run_action(lambda: manager.complete_follow_up(follow_up_id, not item["completed"]),
                       "Follow-up status updated.")
        confirm = st.checkbox("Confirm follow-up deletion", key="confirm_delete_follow_up")
        if st.button("Delete follow-up", disabled=not confirm, key="delete_follow_up"):
            run_action(lambda: manager.delete_follow_up(follow_up_id), "Follow-up deleted.")
    else:
        st.info("No follow-ups for the selected record.")

    st.subheader("Interaction history")
    notes = sorted(owner.notes, key=lambda item: item["date"])
    if notes:
        for index, note in enumerate(notes):
            if index == len(notes) - 1:
                st.caption("Latest interaction")
            st.markdown(f"**{note['date']} · {note['interaction_type']}**")
            st.write(note["description"])
    else:
        st.info("No interaction notes for this record yet.")
    with st.form("add_interaction_note"):
        interaction_type = st.selectbox("Interaction type", INTERACTION_TYPES, key="new_note_type")
        note_text = st.text_area("Note", key="new_note_description")
        add_note = st.form_submit_button("Add interaction note", key="submit_add_note")
    if add_note:
        try:
            manager.add_interaction_note(owner_type, owner_id, interaction_type, note_text)
        except Exception as error:
            show_error("Interaction note", error)
        else:
            finish_action("Interaction note added.")


st.title("Customer and Lead Management")
show_message()
page = st.sidebar.radio("Page", ["Dashboard", "Customers", "Leads", "Follow-ups & Notes"])
if page == "Dashboard":
    render_dashboard()
elif page == "Customers":
    render_customers()
elif page == "Leads":
    render_leads()
else:
    render_follow_ups_and_notes()
