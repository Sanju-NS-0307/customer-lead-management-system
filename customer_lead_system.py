
import streamlit as st
from customer_lead import CustomerLeadManager

st.set_page_config(
    page_title="Customer & Lead Management",
    page_icon="📊",
    layout="wide",
)

# Streamlit reruns this script after interactions.
# Keep one manager instance for the current session.
if "manager" not in st.session_state:
    st.session_state.manager = CustomerLeadManager()

manager = st.session_state.manager

st.title("Customer & Lead Management System")
st.caption("Manage customer records and track potential customers.")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Add Customer",
        "Add Lead",
        "Manage Leads",
        "Search Records",
    ],
)

if page == "Dashboard":
    st.header("Dashboard")

    total_customers = len(manager.customers)
    total_leads = len(manager.leads)
    interested_leads = sum(
        lead.status == "Interested"
        for lead in manager.leads.values()
    )
    converted_leads = sum(
        lead.status == "Converted"
        for lead in manager.leads.values()
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Customers", total_customers)
    col2.metric("Total Leads", total_leads)
    col3.metric("Interested Leads", interested_leads)
    col4.metric("Converted Leads", converted_leads)

    st.subheader("Recent Leads")
    recent_leads = list(manager.leads.values())[-5:][::-1]

    if recent_leads:
        st.dataframe(
            [
                {
                    "Lead ID": lead.lead_id,
                    "Name": lead.name,
                    "Phone": lead.phone,
                    "Source": lead.source,
                    "Status": lead.status,
                }
                for lead in recent_leads
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No leads registered yet.")

elif page == "Add Customer":
    st.header("Register a Customer")

    with st.form("customer_form"):
        name = st.text_input("Full Name")
        phone = st.text_input("10-digit Phone Number")
        email = st.text_input("Email Address")
        category = st.selectbox(
            "Customer Category",
            ["Regular", "Premium", "Business"],
        )

        submitted = st.form_submit_button("Register Customer")

    if submitted:
        try:
            customer = manager.add_customer(
                name, phone, email, category
            )
            st.success(
                f"Customer registered successfully! ID: {customer.customer_id}"
            )
        except ValueError as error:
            st.error(str(error))
        except OSError as error:
            st.error(f"Could not save customer data: {error}")

elif page == "Add Lead":
    st.header("Register a Lead")

    with st.form("lead_form"):
        name = st.text_input("Lead Name")
        phone = st.text_input("10-digit Phone Number")
        email = st.text_input("Email Address")
        source = st.selectbox(
            "Lead Source",
            ["Website", "Referral", "Social Media", "Advertisement", "Other"],
        )

        submitted = st.form_submit_button("Register Lead")

    if submitted:
        try:
            lead = manager.add_lead(name, phone, email, source)
            st.success(
                f"Lead registered successfully! ID: {lead.lead_id}"
            )
        except ValueError as error:
            st.error(str(error))
        except OSError as error:
            st.error(f"Could not save lead data: {error}")

elif page == "Manage Leads":
    st.header("Manage Lead Status")

    if not manager.leads:
        st.info("No leads available. Register a lead first.")
    else:
        lead_ids = list(manager.leads.keys())
        selected_id = st.selectbox("Select Lead", lead_ids)
        selected_lead = manager.leads[selected_id]

        st.write(f"**Name:** {selected_lead.name}")
        st.write(f"**Current status:** {selected_lead.status}")

        with st.form("status_form"):
            new_status = st.selectbox(
                "New Status",
                LeadStatuses := [
                    "New",
                    "Contacted",
                    "Interested",
                    "Converted",
                    "Lost",
                ],
                index=LeadStatuses.index(selected_lead.status),
            )
            submitted = st.form_submit_button("Update Status")

        if submitted:
            try:
                manager.update_lead_status(selected_id, new_status)
                st.success("Lead status updated and saved.")
                st.rerun()
            except (ValueError, OSError) as error:
                st.error(str(error))

        st.subheader("All Leads")
        st.dataframe(
            [
                {
                    "Lead ID": lead.lead_id,
                    "Name": lead.name,
                    "Phone": lead.phone,
                    "Source": lead.source,
                    "Status": lead.status,
                }
                for lead in manager.leads.values()
            ],
            use_container_width=True,
            hide_index=True,
        )

elif page == "Search Records":
    st.header("Search Customers and Leads")
    search_term = st.text_input("Enter an ID, name, or phone number")

    if search_term.strip():
        st.subheader("Customers")
        customers = manager.search_customers(search_term)

        if customers:
            st.dataframe(
                [
                    {
                        "Customer ID": c.customer_id,
                        "Name": c.name,
                        "Phone": c.phone,
                        "Email": c.email,
                        "Category": c.category,
                    }
                    for c in customers
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No matching customers found.")

        st.subheader("Leads")
        leads = manager.search_leads(search_term)

        if leads:
            st.dataframe(
                [
                    {
                        "Lead ID": lead.lead_id,
                        "Name": lead.name,
                        "Phone": lead.phone,
                        "Email": lead.email,
                        "Status": lead.status,
                    }
                    for lead in leads
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No matching leads found.")
