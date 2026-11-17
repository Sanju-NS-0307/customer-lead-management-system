from datetime import date

import streamlit as st

from customer_lead import CustomerLeadManager


st.set_page_config(page_title="Customer and Lead Management", layout="wide")

if "manager" not in st.session_state:
    st.session_state.manager = CustomerLeadManager()

manager = st.session_state.manager


def show_success_after_rerun(message):
    st.session_state["_flash_feedback"] = message
    st.rerun()


def show_action_error(action, error):
    if isinstance(error, ValueError):
        st.error(f"{action} was not completed: {error}")
    elif isinstance(error, OSError):
        st.error(f"{action} could not be saved. Check storage and try again.")
    else:
        st.error(f"{action} could not be completed. Please try again.")


def show_feedback():
    message = st.session_state.pop("_flash_feedback", None)
    if message:
        st.success(message)


def customer_form():
    with st.form("customer_form"):
        name = st.text_input("Full name", key="customer_name")
        phone = st.text_input("10-digit phone number", key="customer_phone")
        email = st.text_input("Email address", key="customer_email")
        category = st.selectbox(
            "Category", ["Regular", "Premium", "Business"], key="customer_category"
        )
        submitted = st.form_submit_button("Register customer")

    if submitted:
        try:
            customer = manager.add_customer(name, phone, email, category)
        except Exception as error:
            show_action_error("Customer registration", error)
        else:
            show_success_after_rerun(
                f"Customer registered. ID: {customer.customer_id}"
            )


def lead_form():
    with st.form("lead_form"):
        name = st.text_input("Full name", key="lead_name")
        phone = st.text_input("10-digit phone number", key="lead_phone")
        email = st.text_input("Email address", key="lead_email")
        source = st.selectbox(
            "Source",
            ["Website", "Referral", "Social Media", "Advertisement", "Other"],
            key="lead_source",
        )
        submitted = st.form_submit_button("Register lead")

    if submitted:
        try:
            lead = manager.add_lead(name, phone, email, source)
        except Exception as error:
            show_action_error("Lead registration", error)
        else:
            show_success_after_rerun(f"Lead registered. ID: {lead.lead_id}")


def render_dashboard():
    st.header("Dashboard")
    st.metric("Total customers", len(manager.customers))
    st.metric("Total leads", len(manager.leads))
    st.subheader("Lead status")
    statuses = ("New", "Contacted", "Interested", "Converted", "Lost")
    st.dataframe(
        [
            {
                "Status": status,
                "Leads": sum(lead.status == status for lead in manager.leads.values()),
            }
            for status in statuses
        ],
        hide_index=True,
        width="stretch",
        alt="Lead counts by status",
    )


def render_customers():
    st.header("Customers")
    st.subheader("Register a customer")
    customer_form()

    st.subheader("Customer list")
    if not manager.customers:
        st.info("No customers yet. Register a customer above to get started.")
        return

    query = st.text_input(
        "Search by customer ID, name, or phone", key="customer_search"
    )
    customers = (
        manager.search_customers(query)
        if query.strip()
        else list(manager.customers.values())
    )
    if not customers:
        st.info("No customers match that search.")
        return

    st.dataframe(
        [
            {
                "Customer ID": customer.customer_id,
                "Name": customer.name,
                "Category": customer.category,
            }
            for customer in customers
        ],
        hide_index=True,
        width="stretch",
        alt="Customer list",
    )
    customer_id = st.selectbox(
        "View customer details",
        [customer.customer_id for customer in customers],
        key="customer_selected_id",
    )
    customer = manager.customers[customer_id]
    with st.container(border=True):
        st.subheader("Customer details")
        st.write(f"**ID:** {customer.customer_id}")
        st.write(f"**Name:** {customer.name}")
        st.write(f"**Phone:** {customer.phone}")
        st.write(f"**Email:** {customer.email}")
        st.write(f"**Category:** {customer.category}")


def render_leads():
    st.header("Leads")
    st.subheader("Register a lead")
    lead_form()

    st.subheader("Lead list")
    if not manager.leads:
        st.info("No leads yet. Register a lead above to get started.")
        return

    search_column, status_column = st.columns(2)
    query = search_column.text_input(
        "Search by lead ID, name, or phone", key="lead_search"
    )
    status_filter = status_column.selectbox(
        "Filter by status",
        ["All statuses", "New", "Contacted", "Interested", "Converted", "Lost"],
        key="lead_status_filter",
    )
    leads = manager.search_leads(query) if query.strip() else list(manager.leads.values())
    if status_filter != "All statuses":
        leads = [lead for lead in leads if lead.status == status_filter]
    if not leads:
        st.info("No leads match the current search and status filter.")
        return

    st.dataframe(
        [
            {
                "Lead ID": lead.lead_id,
                "Name": lead.name,
                "Source": lead.source,
                "Status": lead.status,
            }
            for lead in leads
        ],
        hide_index=True,
        width="stretch",
        alt="Lead list",
    )
    lead_id = st.selectbox(
        "Select a lead", [lead.lead_id for lead in leads], key="lead_selected_id"
    )
    lead = manager.leads[lead_id]
    st.write(f"**Name:** {lead.name}  \n**Status:** {lead.status}")
    if lead.status != "Converted":
        valid_statuses = ["New", "Contacted", "Interested", "Lost"]
        with st.form("lead_status_form"):
            new_status = st.selectbox(
                "Update status",
                valid_statuses,
                index=valid_statuses.index(lead.status),
                key="lead_new_status",
            )
            submitted = st.form_submit_button("Save status")
        if submitted:
            try:
                manager.update_lead_status(lead_id, new_status)
            except Exception as error:
                show_action_error("Lead status update", error)
            else:
                show_success_after_rerun("Lead status updated.")


def render_follow_ups_and_notes():
    st.header("Follow-ups & Notes")

    overdue = manager.get_overdue_follow_ups()
    upcoming = manager.get_upcoming_follow_ups()
    st.subheader("Overdue follow-ups")
    if overdue:
        st.dataframe(
            [
                {"Due date": lead.follow_up_date, "Lead ID": lead.lead_id,
                 "Name": lead.name, "Status": lead.status}
                for lead in overdue
            ],
            hide_index=True,
            width="stretch",
            alt="Overdue follow-ups",
        )
    else:
        st.info("No overdue follow-ups.")

    st.subheader("Upcoming follow-ups")
    if upcoming:
        st.dataframe(
            [
                {"Due date": lead.follow_up_date, "Lead ID": lead.lead_id,
                 "Name": lead.name, "Status": lead.status}
                for lead in upcoming
            ],
            hide_index=True,
            width="stretch",
            alt="Upcoming follow-ups",
        )
    else:
        st.info("No upcoming follow-ups in the next seven days.")

    if not manager.leads:
        st.info("No leads are available for follow-ups or notes yet.")
        return

    st.subheader("Lead activity")
    lead_id = st.selectbox(
        "Select a lead", list(manager.leads), key="activity_lead_id"
    )
    lead = manager.leads[lead_id]

    st.subheader("Follow-up date")
    if lead.follow_up_date:
        st.caption(f"Current date: {lead.follow_up_date}")
    else:
        st.caption("No follow-up date is set.")

    clear_key = f"clear_follow_up_{lead_id}"
    if lead.follow_up_date is None:
        st.session_state[clear_key] = False
    with st.form(f"follow_up_form_{lead_id}"):
        clear_date = st.checkbox(
            "Clear follow-up date",
            disabled=lead.follow_up_date is None,
            key=clear_key,
        )
        current_date = (
            date.fromisoformat(lead.follow_up_date)
            if lead.follow_up_date
            else date.today()
        )
        selected_date = st.date_input(
            "Follow-up date", value=current_date, key=f"follow_up_date_{lead_id}"
        )
        save_date = st.form_submit_button("Save follow-up")
    if save_date:
        try:
            manager.set_lead_follow_up(lead_id, None if clear_date else selected_date)
        except Exception as error:
            show_action_error("Follow-up update", error)
        else:
            show_success_after_rerun(
                "Follow-up date cleared." if clear_date else "Follow-up date saved."
            )

    st.subheader("Interaction history")
    if lead.notes:
        notes = sorted(lead.notes, key=lambda item: item["date"])
        for index, note in enumerate(notes):
            if index == len(notes) - 1:
                st.caption("Latest interaction")
            st.markdown(f"**Date:** {note['date']} | **Type:** {note['interaction_type']}")
            st.write(note["description"])
    else:
        st.info("No interaction notes for this lead yet.")

    with st.form("interaction_note_form"):
        interaction_type = st.selectbox(
            "Interaction type", ["Call", "Email", "Meeting", "Other"]
        )
        description = st.text_area("Description", key="interaction_description")
        save_note = st.form_submit_button("Add note")
    if save_note:
        try:
            manager.add_interaction_note(lead_id, interaction_type, description)
        except Exception as error:
            show_action_error("Interaction note", error)
        else:
            show_success_after_rerun("Interaction note added.")


st.title("Customer and Lead Management")
show_feedback()
page = st.sidebar.radio(
    "Page", ["Dashboard", "Customers", "Leads", "Follow-ups & Notes"]
)

if page == "Dashboard":
    render_dashboard()
elif page == "Customers":
    render_customers()
elif page == "Leads":
    render_leads()
else:
    render_follow_ups_and_notes()
