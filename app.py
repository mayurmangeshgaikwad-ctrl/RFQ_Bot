import sqlite3
import streamlit as st

from database import (
    create_database,
    save_rfq,
    get_rfqs,
    get_inventory,
    get_inventory_product,
    reduce_inventory,
    update_rfq_status,
    save_sent_quote,
    DATABASE_NAME
)

from business_data import find_customer_history

from quote_generator import (
    create_quote_line,
    create_client_quote
)


create_database()

st.set_page_config(
    page_title="RFQ Control Center",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stSidebar"] {display: none;}

    .block-container {
        max-width: 1480px;
        padding-top: 1rem;
        padding-bottom: 3rem;
    }

    .app-header {
        background: linear-gradient(135deg, #07152f 0%, #13245f 55%, #2b145b 100%);
        border-radius: 18px;
        padding: 28px 32px;
        margin-bottom: 22px;
        border: 1px solid rgba(255,255,255,0.08);
    }

    .app-header h1 {
        color: #ffffff;
        font-size: 31px;
        margin: 0;
        font-weight: 800;
    }

    .app-header p {
        color: rgba(255,255,255,0.72);
        margin: 8px 0 0 0;
        font-size: 14px;
    }

    .nav-status {
        text-align: right;
        padding-top: 12px;
        color: #62dfab;
        font-size: 12px;
        font-weight: 700;
    }

    .section-title {
        font-size: 20px;
        font-weight: 750;
        margin: 25px 0 12px 0;
    }

    .metric-card {
        border: 1px solid rgba(128,128,128,0.18);
        border-radius: 15px;
        padding: 20px;
        min-height: 125px;
        background: rgba(128,128,128,0.035);
    }

    .metric-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1px;
        opacity: 0.55;
        font-weight: 700;
    }

    .metric-value {
        font-size: 33px;
        font-weight: 800;
        margin-top: 8px;
    }

    .metric-description {
        font-size: 12px;
        opacity: 0.55;
        margin-top: 5px;
    }

    .panel {
        border: 1px solid rgba(128,128,128,0.18);
        border-radius: 15px;
        padding: 20px;
        background: rgba(128,128,128,0.03);
        margin-bottom: 14px;
    }

    .panel-title {
        font-size: 16px;
        font-weight: 750;
    }

    .panel-text {
        font-size: 13px;
        line-height: 1.55;
        opacity: 0.62;
        margin-top: 7px;
    }

    div.stButton > button {
        border-radius: 9px;
        min-height: 42px;
        font-weight: 650;
    }

    div[data-testid="stMetric"] {
        border: 1px solid rgba(128,128,128,0.18);
        border-radius: 15px;
        padding: 14px;
    }

    .top-space {
        margin-top: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


emails = [
    {
        "id": 1,
        "sender": "purchasing@abc-chemicals.com",
        "customer": "mayur Chemicals",
        "subject": "RFQ - Acetone - 500 KG",
        "body": """Dear Sales Team,

Please provide your best price for the following:

Product: Acetone
CAS Number: 67-64-1
Quantity: 500 KG
Required delivery: 15 September

Regards,
mayur Chemicals Purchasing Team"""
    },
    {
        "id": 2,
        "sender": "accounts@xyz-industries.com",
        "customer": "Sejal Industries",
        "subject": "Previous Invoice",
        "body": """Dear Team,

Could you please send us a copy of our previous invoice?

Thank you."""
    },
    {
        "id": 3,
        "sender": "purchase@global-labs.com",
        "customer": "GlobalEd Labs",
        "subject": "Quotation Request - Methanol",
        "body": """Hello,

We would like a quotation for:

Product: Methanol
CAS Number: 67-56-1
Quantity: 200 KG
Required delivery: 20 September

Please include price and delivery time.

Regards,
GlobalEd Labs"""
    },
    {
        "id": 4,
        "sender": "procurement@mega-industries.com",
        "customer": "Iron Industries",
        "subject": "RFQ - Acetone and Specialty Chemical X",
        "body": """Dear Sales Team,

Please provide your best quotation for the following products:

Product: Acetone
CAS Number: 67-64-1
Quantity: 500 KG

Product: Specialty Chemical X
Quantity: 100 KG

Please include price and delivery time.

Regards,
Iron Industries"""
    }
]


if "page" not in st.session_state:
    st.session_state["page"] = "Dashboard"


def go_to(page):
    st.session_state["page"] = page
    st.rerun()


def check_inventory(product, requested_quantity):
    item = get_inventory_product(product)

    if item is None:
        return {
            "status": "Not Available",
            "available": 0,
            "price": 0,
            "unit": "",
            "total_amount": 0,
            "message": f"{product} is not available in our inventory."
        }

    available_quantity = float(item[3])
    price = float(item[5])
    unit = item[4]
    requested_quantity = float(requested_quantity)

    if requested_quantity <= available_quantity:
        total_amount = requested_quantity * price
        return {
            "status": "Available",
            "available": available_quantity,
            "price": price,
            "unit": unit,
            "total_amount": total_amount,
            "message": "Inventory is sufficient."
        }

    return {
        "status": "Insufficient",
        "available": available_quantity,
        "price": price,
        "unit": unit,
        "total_amount": 0,
        "message": (
            f"Requested {requested_quantity} {unit}, "
            f"but only {available_quantity} {unit} is available."
        )
    }


def detect_rfq(email):
    text = (email["subject"] + " " + email["body"]).lower()
    rfq_words = [
        "rfq",
        "quotation",
        "quote",
        "quotation request",
        "price",
        "best price",
        "commercial offer",
        "pricing",
        "please quote"
    ]
    return any(word in text for word in rfq_words)


def extract_rfq_information(email):
    line_items = []
    current_item = None

    for raw_line in email["body"].split("\n"):
        line = raw_line.strip()

        if line.lower().startswith("product:"):
            if current_item is not None:
                line_items.append(current_item)

            current_item = {
                "customer": email["customer"],
                "product": line.split(":", 1)[1].strip(),
                "cas_number": "Unknown",
                "quantity": "Unknown",
                "delivery_date": "Unknown"
            }

        elif line.lower().startswith("cas number:") and current_item:
            current_item["cas_number"] = line.split(":", 1)[1].strip()

        elif line.lower().startswith("cas:") and current_item:
            current_item["cas_number"] = line.split(":", 1)[1].strip()

        elif line.lower().startswith("quantity:") and current_item:
            current_item["quantity"] = line.split(":", 1)[1].strip()

        elif line.lower().startswith("required delivery:") and current_item:
            current_item["delivery_date"] = line.split(":", 1)[1].strip()

    if current_item is not None:
        line_items.append(current_item)

    return line_items


def find_saved_rfq(customer, product):
    for rfq in get_rfqs():
        if (
            rfq[1] == customer
            and rfq[2].lower() == product.lower()
        ):
            return rfq
    return None


def is_email_processed(email):
    for rfq in get_rfqs():
        if len(rfq) < 7:
            continue

        if (
            rfq[1] == email["customer"]
            and rfq[2].lower() in email["body"].lower()
            and rfq[6] in ["Approved", "Rejected"]
        ):
            return True

    return False


def get_dashboard_counts():
    rfqs = get_rfqs()
    inventory = get_inventory()

    pending = sum(
        1 for rfq in rfqs
        if rfq[6] not in ["Approved", "Rejected"]
    )

    approved = sum(
        1 for rfq in rfqs
        if rfq[6] == "Approved"
    )

    inbox = sum(
        1 for email in emails
        if detect_rfq(email) and not is_email_processed(email)
    )

    return pending, inbox, len(inventory), approved


def get_db_inventory_dict(product):
    item = get_inventory_product(product)

    if item is None:
        return None, None

    inventory = {
        "product": item[1],
        "cas_number": item[2],
        "available_quantity": float(item[3]),
        "unit": item[4],
        "price": float(item[5]),
        "currency": item[6]
    }

    price = {
        "product": item[1],
        "price": float(item[5]),
        "unit": item[4],
        "currency": item[6]
    }

    return inventory, price


def create_quote_for_rfq(rfq):
    rfq_id, customer, product, cas_number, quantity_text, delivery_date, status, total_amount = rfq

    try:
        quantity = float(str(quantity_text).split()[0])
    except (ValueError, IndexError):
        quantity = None

    inventory, price = get_db_inventory_dict(product)

    item = {
        "customer": customer,
        "product": product,
        "cas_number": cas_number,
        "quantity": quantity_text,
        "delivery_date": delivery_date
    }

    history = find_customer_history(
        customer,
        product
    )

    quote_line = create_quote_line(
        item,
        inventory,
        price
    )

    quote = create_client_quote(
        customer,
        [quote_line]
    )

    st.session_state["quote_rfq_id"] = rfq_id
    st.session_state["quote_customer"] = customer
    st.session_state["quote_product"] = product
    st.session_state["quote_quantity"] = quantity
    st.session_state["quote_unit"] = (
        inventory["unit"] if inventory else ""
    )
    st.session_state["quote_total"] = (
        quantity * price["price"]
        if quantity is not None and price
        else float(total_amount or 0)
    )
    st.session_state["quote_status"] = "Pending Review"
    st.session_state["draft_quote"] = quote
    st.session_state["quote_history"] = history
    go_to("Quote Review")


def add_product_to_database(product, cas_number, quantity, unit, price, currency):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO inventory
            (product, cas_number, available_quantity, unit, price, currency)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                product.strip(),
                cas_number.strip(),
                float(quantity),
                unit.strip().upper(),
                float(price),
                currency.strip().upper()
            )
        )
        connection.commit()
        return True, "Product added successfully."
    except sqlite3.IntegrityError:
        return False, "This product already exists in inventory."
    finally:
        connection.close()


def render_top_navigation():
    nav_items = [
        ("Dashboard", "Dashboard"),
        ("RFQ Inbox", "RFQ Inbox"),
        ("RFQ Records", "RFQ Records"),
        ("Inventory", "Inventory"),
        ("Quote Review", "Quote Review")
    ]

    menu_col, brand_col, *nav_cols, status_col = st.columns(
        [0.6, 2.1, 1.0, 1.0, 1.1, 1.0, 1.1, 1.2]
    )

    with menu_col:
        with st.popover("☰", use_container_width=True):
            st.markdown("### Navigation")

            if st.button(
                "Dashboard",
                use_container_width=True,
                key="menu_dashboard"
            ):
                go_to("Dashboard")

            if st.button(
                "Manual RFQ",
                use_container_width=True,
                key="menu_manual_rfq"
            ):
                go_to("Manual RFQ")

            if st.button(
                "Add Product",
                use_container_width=True,
                key="menu_add_product"
            ):
                go_to("Add Product")

            if st.button(
                "RFQ Inbox",
                use_container_width=True,
                key="menu_inbox"
            ):
                go_to("RFQ Inbox")

            if st.button(
                "RFQ Records",
                use_container_width=True,
                key="menu_records"
            ):
                go_to("RFQ Records")

            if st.button(
                "Inventory",
                use_container_width=True,
                key="menu_inventory"
            ):
                go_to("Inventory")

            if st.button(
                "Quote Review",
                use_container_width=True,
                key="menu_review"
            ):
                go_to("Quote Review")

    with brand_col:
        st.markdown(
            '<div class="top-space"><strong>RFQ Control Center</strong><br><span style="font-size:11px;opacity:.55">Chemical Procurement Operations</span></div>',
            unsafe_allow_html=True
        )

    for column, (label, page) in zip(nav_cols, nav_items):
        with column:
            button_type = "primary" if st.session_state["page"] == page else "secondary"
            if st.button(
                label,
                use_container_width=True,
                key=f"top_{page.lower().replace(' ', '_')}",
                type=button_type
            ):
                go_to(page)

    with status_col:
        st.markdown(
            '<div class="nav-status">SYSTEM ONLINE</div>',
            unsafe_allow_html=True
        )


render_top_navigation()


pending_count, inbox_count, inventory_count, approved_count = get_dashboard_counts()


if st.session_state["page"] == "Dashboard":

    st.markdown(
        """
        <div class="app-header">
            <h1>Welcome to RFQ Control Center</h1>
            <p>Monitor customer requests, manage chemical inventory and control quotation approvals.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="section-title">Operations Overview</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Pending RFQs", pending_count, "Awaiting processing")

    with c2:
        st.metric("Inbox", inbox_count, "RFQ emails available")

    with c3:
        st.metric("Inventory", inventory_count, "Products in stock")

    with c4:
        st.metric("Approved", approved_count, "Completed RFQs")

    st.markdown(
        '<div class="section-title">Quick Actions</div>',
        unsafe_allow_html=True
    )

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        with st.container(border=True):
            st.subheader("RFQ Inbox")
            st.write("Review incoming emails and detect customer RFQs.")
            st.caption(f"{inbox_count} RFQ emails available")
            if st.button("Open Inbox", use_container_width=True, key="dash_inbox"):
                go_to("RFQ Inbox")

    with a2:
        with st.container(border=True):
            st.subheader("Manual RFQ")
            st.write("Create an RFQ directly when a request arrives outside email.")
            st.caption("Employee entry")
            if st.button("Create RFQ", use_container_width=True, key="dash_manual_rfq"):
                go_to("Manual RFQ")

    with a3:
        with st.container(border=True):
            st.subheader("Inventory")
            st.write("Manage current company chemical stock and internal pricing.")
            st.caption(f"{inventory_count} products registered")
            if st.button("Open Inventory", use_container_width=True, key="dash_inventory"):
                go_to("Inventory")

    with a4:
        with st.container(border=True):
            st.subheader("Add Product")
            st.write("Add a new chemical directly into the SQLite inventory database.")
            st.caption("Inventory management")
            if st.button("Add Product", use_container_width=True, key="dash_add_product"):
                go_to("Add Product")

    st.markdown(
        '<div class="section-title">Recent RFQ Activity</div>',
        unsafe_allow_html=True
    )

    rfqs = get_rfqs()

    if rfqs:
        for rfq in reversed(rfqs[-5:]):
            with st.container(border=True):
                ac1, ac2, ac3, ac4 = st.columns(4)
                with ac1:
                    st.caption("RFQ")
                    st.write(f"#{rfq[0]}")
                with ac2:
                    st.caption("CUSTOMER")
                    st.write(rfq[1])
                with ac3:
                    st.caption("PRODUCT")
                    st.write(rfq[2])
                with ac4:
                    st.caption("STATUS")
                    st.write(rfq[6])
    else:
        st.info("No RFQ activity has been recorded yet.")


elif st.session_state["page"] == "RFQ Inbox":

    st.markdown(
        """
        <div class="app-header">
            <h1>RFQ Inbox</h1>
            <p>Incoming customer communication and automated RFQ detection.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    visible_emails = [
        email for email in emails
        if not is_email_processed(email)
    ]

    if not visible_emails:
        st.success("No unprocessed RFQ emails are currently in the inbox.")

    for email in visible_emails:

        with st.expander(
            f"{email['subject']}  |  {email['sender']}"
        ):

            st.write("Customer:", email["customer"])
            st.write("Sender:", email["sender"])
            st.write("Subject:", email["subject"])
            st.write("Email Content")
            st.text(email["body"])

            if not detect_rfq(email):
                st.warning("This message is not an RFQ.")
                continue

            st.success("RFQ detected")

            line_items = extract_rfq_information(email)
            quote_lines = []

            st.markdown(
                '<div class="section-title">RFQ Details</div>',
                unsafe_allow_html=True
            )

            for number, item in enumerate(line_items, start=1):

                try:
                    requested_quantity = float(
                        item["quantity"].split()[0]
                    )
                except (ValueError, IndexError):
                    requested_quantity = None

                if requested_quantity is None:
                    st.error(
                        f"Could not read quantity for {item['product']}: {item['quantity']}"
                    )
                    continue

                result = check_inventory(
                    item["product"],
                    requested_quantity
                )

                with st.container(border=True):

                    c1, c2, c3, c4 = st.columns(4)

                    with c1:
                        st.caption("PRODUCT")
                        st.write(item["product"])

                    with c2:
                        st.caption("REQUESTED")
                        st.write(
                            f"{requested_quantity} {result['unit']}"
                        )

                    with c3:
                        st.caption("AVAILABLE")
                        st.write(
                            f"{result['available']} {result['unit']}"
                        )

                    with c4:
                        st.caption("PRICE")
                        st.write(
                            f"₹{result['price']} / {result['unit']}"
                        )

                    if result["status"] == "Available":
                        st.success(
                            f"Inventory sufficient. Total: ₹{result['total_amount']:,.2f}"
                        )
                    elif result["status"] == "Insufficient":
                        st.warning(result["message"])
                    else:
                        st.error(result["message"])

            st.markdown(
                '<div class="section-title">Supporting Information</div>',
                unsafe_allow_html=True
            )

            for item in line_items:

                inventory, price = get_db_inventory_dict(
                    item["product"]
                )

                history = find_customer_history(
                    item["customer"],
                    item["product"]
                )

                ci1, ci2, ci3 = st.columns(3)

                with ci1:
                    st.caption("INVENTORY")
                    if inventory:
                        st.write(
                            f"{inventory['available_quantity']} {inventory['unit']} available"
                        )
                    else:
                        st.warning("Not available in-house")

                with ci2:
                    st.caption("PRICE")
                    if price:
                        st.write(
                            f"{price['currency']} {price['price']} / {price['unit']}"
                        )
                    else:
                        st.warning("No internal price")

                with ci3:
                    st.caption("CUSTOMER HISTORY")
                    if history:
                        st.write(
                            f"Last order: {history['last_quantity']}"
                        )
                        st.caption(
                            f"Last price: {history['last_price']}"
                        )
                    else:
                        st.write("No previous order")

                quote_lines.append(
                    create_quote_line(
                        item,
                        inventory,
                        price
                    )
                )

            st.divider()

            b1, b2 = st.columns(2)

            with b1:
                if st.button(
                    "Save RFQ to CRM",
                    key=f"save_email_{email['id']}",
                    use_container_width=True
                ):
                    for item in line_items:
                        save_rfq(item)

                    st.success("RFQ saved to CRM.")
                    go_to("RFQ Records")

            with b2:
                if st.button(
                    "Generate Draft Quote",
                    key=f"quote_email_{email['id']}",
                    use_container_width=True
                ):
                    quote = create_client_quote(
                        email["customer"],
                        quote_lines
                    )

                    if line_items:

                        first_item = line_items[0]
                        product = first_item["product"]
                        customer = email["customer"]

                        try:
                            requested_quantity = float(
                                first_item["quantity"].split()[0]
                            )
                        except (ValueError, IndexError):
                            requested_quantity = None

                        saved_rfq = find_saved_rfq(
                            customer,
                            product
                        )

                        st.session_state["quote_rfq_id"] = (
                            saved_rfq[0]
                            if saved_rfq
                            else None
                        )

                        st.session_state["quote_customer"] = customer
                        st.session_state["quote_product"] = product
                        st.session_state["quote_quantity"] = requested_quantity

                        inventory_result = (
                            check_inventory(
                                product,
                                requested_quantity
                            )
                            if requested_quantity is not None
                            else None
                        )

                        st.session_state["quote_unit"] = (
                            inventory_result["unit"]
                            if inventory_result
                            else ""
                        )

                        st.session_state["quote_total"] = (
                            inventory_result["total_amount"]
                            if (
                                inventory_result
                                and inventory_result["status"] == "Available"
                            )
                            else 0
                        )

                        st.session_state["quote_status"] = "Pending Review"

                    st.session_state["draft_quote"] = quote
                    go_to("Quote Review")


elif st.session_state["page"] == "Manual RFQ":

    st.markdown(
        """
        <div class="app-header">
            <h1>Manual RFQ Entry</h1>
            <p>Create a customer RFQ when the request is received outside the email inbox.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.form("manual_rfq_form"):

        c1, c2 = st.columns(2)

        with c1:
            customer = st.text_input(
                "Customer Name",
                placeholder="Example: ABC Chemicals"
            )

            product = st.text_input(
                "Product",
                placeholder="Example: Acetone"
            )

            cas_number = st.text_input(
                "CAS Number",
                placeholder="Example: 67-64-1"
            )

        with c2:
            quantity = st.number_input(
                "Quantity",
                min_value=0.01,
                step=1.0
            )

            unit = st.selectbox(
                "Unit",
                ["KG", "L", "MT", "G", "ML"]
            )

            delivery_date = st.text_input(
                "Required Delivery",
                placeholder="Example: 25 September"
            )

        submitted = st.form_submit_button(
            "Save RFQ",
            use_container_width=True
        )

    if submitted:

        if not customer.strip():
            st.error("Customer name is required.")

        elif not product.strip():
            st.error("Product is required.")

        elif quantity <= 0:
            st.error("Quantity must be greater than zero.")

        elif not delivery_date.strip():
            st.error("Required delivery is required.")

        else:

            rfq = {
                "customer": customer.strip(),
                "product": product.strip(),
                "cas_number": cas_number.strip() or "Unknown",
                "quantity": f"{quantity:g} {unit}",
                "delivery_date": delivery_date.strip()
            }

            save_rfq(rfq)

            st.success(
                "RFQ saved successfully and added to RFQ Records."
            )

            st.session_state["manual_rfq_message"] = (
                customer.strip(),
                product.strip()
            )

    if "manual_rfq_message" in st.session_state:
        customer_name, product_name = st.session_state[
            "manual_rfq_message"
        ]

        latest = find_saved_rfq(
            customer_name,
            product_name
        )

        if latest:
            st.divider()

            if st.button(
                "Generate Draft Quote for This RFQ",
                use_container_width=True,
                key="manual_generate_quote"
            ):
                create_quote_for_rfq(latest)

            if st.button(
                "Open RFQ Records",
                use_container_width=True,
                key="manual_open_records"
            ):
                go_to("RFQ Records")


elif st.session_state["page"] == "Add Product":

    st.markdown(
        """
        <div class="app-header">
            <h1>Add Product to Inventory</h1>
            <p>Add a new chemical directly to the company SQLite inventory database.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.form("add_inventory_form"):

        c1, c2 = st.columns(2)

        with c1:
            product = st.text_input(
                "Product Name",
                placeholder="Example: Toluene"
            )

            cas_number = st.text_input(
                "CAS Number",
                placeholder="Example: 108-88-3"
            )

            quantity = st.number_input(
                "Available Quantity",
                min_value=0.0,
                step=1.0
            )

        with c2:
            unit = st.selectbox(
                "Unit",
                ["KG", "L", "MT", "G", "ML"]
            )

            price = st.number_input(
                "Price per Unit",
                min_value=0.0,
                step=1.0
            )

            currency = st.text_input(
                "Currency",
                value="INR"
            )

        submitted = st.form_submit_button(
            "Add Product",
            use_container_width=True
        )

    if submitted:

        if not product.strip():
            st.error("Product name is required.")

        elif not cas_number.strip():
            st.error("CAS Number is required.")

        elif quantity <= 0:
            st.error("Available quantity must be greater than zero.")

        elif price <= 0:
            st.error("Price must be greater than zero.")

        else:

            success, message = add_product_to_database(
                product,
                cas_number,
                quantity,
                unit,
                price,
                currency
            )

            if success:
                st.success(message)
                st.write(
                    f"{product.strip()} is now available in inventory at "
                    f"{quantity:g} {unit} and {currency.upper()} {price:g} / {unit}."
                )
            else:
                st.error(message)


elif st.session_state["page"] == "RFQ Records":

    st.markdown(
        """
        <div class="app-header">
            <h1>RFQ Records</h1>
            <p>All customer RFQs saved in the CRM database.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    rfqs = get_rfqs()

    if not rfqs:
        st.info("No RFQs have been saved yet.")

    else:

        for rfq in rfqs:

            (
                rfq_id,
                customer,
                product,
                cas_number,
                quantity,
                delivery_date,
                status,
                total_amount
            ) = rfq

            with st.expander(
                f"RFQ #{rfq_id}  |  {customer}  |  {product}"
            ):

                c1, c2, c3 = st.columns(3)

                with c1:
                    st.caption("CUSTOMER")
                    st.write(customer)
                    st.caption("PRODUCT")
                    st.write(product)
                    st.caption("CAS NUMBER")
                    st.write(cas_number)

                with c2:
                    st.caption("QUANTITY")
                    st.write(quantity)
                    st.caption("DELIVERY")
                    st.write(delivery_date)

                with c3:
                    st.caption("STATUS")

                    if status == "Approved":
                        st.success(status)
                    elif status == "Rejected":
                        st.error(status)
                    else:
                        st.warning(status)

                    if total_amount:
                        st.caption("TOTAL AMOUNT")
                        st.write(
                            f"₹{float(total_amount):,.2f}"
                        )

                if status not in ["Approved", "Rejected"]:

                    if st.button(
                        "Generate Draft Quote",
                        key=f"record_quote_{rfq_id}",
                        use_container_width=True
                    ):
                        create_quote_for_rfq(rfq)


elif st.session_state["page"] == "Inventory":

    st.markdown(
        """
        <div class="app-header">
            <h1>Inventory Control</h1>
            <p>Company chemical stock, CAS numbers and internal pricing.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    top1, top2 = st.columns(2)

    with top1:
        st.metric(
            "Products",
            len(get_inventory())
        )

    with top2:
        if st.button(
            "Add New Product",
            use_container_width=True,
            key="inventory_add_product"
        ):
            go_to("Add Product")

    st.divider()

    inventory = get_inventory()

    if not inventory:
        st.info("No inventory found.")

    else:

        for item in inventory:

            product = item[1]
            cas_number = item[2]
            quantity = item[3]
            unit = item[4]
            price = item[5]
            currency = item[6]

            with st.container(border=True):

                c1, c2, c3, c4, c5 = st.columns(5)

                with c1:
                    st.caption("PRODUCT")
                    st.write(product)

                with c2:
                    st.caption("CAS NUMBER")
                    st.write(cas_number)

                with c3:
                    st.caption("AVAILABLE")
                    st.write(f"{quantity:g} {unit}")

                with c4:
                    st.caption("PRICE")
                    st.write(f"{currency} {price:g} / {unit}")

                with c5:
                    st.caption("DATABASE")
                    st.write("Active")


elif st.session_state["page"] == "Quote Review":

    st.markdown(
        """
        <div class="app-header">
            <h1>Human Quote Review</h1>
            <p>Review the quotation before final approval and inventory commitment.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    if "draft_quote" not in st.session_state:

        st.info(
            "No draft quote has been generated yet. Open RFQ Inbox or RFQ Records first."
        )

    else:

        customer = st.session_state.get(
            "quote_customer",
            ""
        )

        rfq_id = st.session_state.get(
            "quote_rfq_id"
        )

        product = st.session_state.get(
            "quote_product",
            ""
        )

        quantity = st.session_state.get(
            "quote_quantity"
        )

        total_amount = st.session_state.get(
            "quote_total",
            0
        )

        unit = st.session_state.get(
            "quote_unit",
            ""
        )

        st.write("Customer:", customer)
        st.write("RFQ:", f"#{rfq_id}" if rfq_id else "Not saved")
        st.write("Product:", product)
        st.write(
            "Quantity:",
            f"{quantity} {unit}" if quantity is not None else "Unknown"
        )
        st.write(
            "Quoted Total:",
            f"₹{float(total_amount):,.2f}"
        )

        st.divider()

        st.text_area(
            "Draft Response",
            value=st.session_state["draft_quote"],
            height=400,
            key="draft_quote_editor"
        )

        st.divider()

        current_status = st.session_state.get(
            "quote_status",
            "Pending Review"
        )

        st.write(
            f"Current status: **{current_status}**"
        )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "Approve Quote",
                key="approve_quote",
                use_container_width=True,
                disabled=current_status in ["Approved", "Rejected"]
            ):

                if rfq_id is None:
                    st.error(
                        "This RFQ has not been saved to CRM."
                    )

                elif product is None or quantity is None:
                    st.error(
                        "Product or quantity information is missing."
                    )

                else:

                    current_rfqs = get_rfqs()
                    database_status = None

                    for row in current_rfqs:
                        if row[0] == rfq_id:
                            database_status = row[6]
                            break

                    if database_status == "Approved":
                        st.warning(
                            "This RFQ is already approved in CRM."
                        )
                        st.session_state["quote_status"] = "Approved"

                    elif database_status == "Rejected":
                        st.warning(
                            "This RFQ is already rejected in CRM."
                        )
                        st.session_state["quote_status"] = "Rejected"

                    else:

                        success, remaining = reduce_inventory(
                            product,
                            quantity,
                            customer,
                            rfq_id
                        )

                        if success:

                            update_rfq_status(
                                rfq_id,
                                "Approved",
                                total_amount
                            )

                            save_sent_quote(
                                customer,
                                product,
                                quantity,
                                total_amount
                            )

                            st.session_state["quote_status"] = "Approved"

                            st.success(
                                "Quote approved successfully."
                            )

                            st.success(
                                f"Inventory updated: {remaining} {unit} remaining."
                            )

                        else:

                            st.error(
                                f"Quote cannot be approved: {remaining}"
                            )

        with c2:

            if st.button(
                "Reject Quote",
                key="reject_quote",
                use_container_width=True,
                disabled=current_status in ["Approved", "Rejected"]
            ):

                if rfq_id is None:
                    st.error(
                        "Save the RFQ to CRM before rejecting it."
                    )

                else:

                    update_rfq_status(
                        rfq_id,
                        "Rejected",
                        0
                    )

                    st.session_state["quote_status"] = "Rejected"

                    st.error(
                        "Quote rejected by reviewer."
                    )

                    st.info(
                        "This RFQ will no longer appear in Inbox."
                    )
