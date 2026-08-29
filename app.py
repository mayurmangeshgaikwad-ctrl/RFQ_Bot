import streamlit as st

from database import (
    create_database,
    save_rfq,
    get_rfqs,
    get_inventory,
    get_inventory_product,
    reduce_inventory,
    update_rfq_status,
    save_sent_quote
)

from business_data import (
    find_inventory,
    find_price,
    find_customer_history
)

from quote_generator import (
    create_quote_line,
    create_client_quote
)


create_database()

st.set_page_config(
    page_title="RFQ Auto-Response Bot",
    layout="wide"
)

st.title("RFQ Auto-Response Bot")

st.write(
    "RFQ detection, information extraction, "
    "business checks and quotation preparation."
)

st.divider()

section = st.selectbox(
    "Select Section",
    [
        "Inbox / RFQ Detection",
        "RFQ Records",
        "Inventory",
        "Quote Review"
    ]
)


def check_inventory(product, requested_quantity):

    item = get_inventory_product(product)

    if item is None:
        return {
            "status": "Not Available",
            "available": 0,
            "price": 0,
            "unit": "",
            "total_amount": 0,
            "message": (
                f"{product} is not available "
                "in our inventory."
            )
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
            f"but only {available_quantity} {unit} "
            "is available."
        )
    }


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

Please include your price and delivery time.

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


def detect_rfq(email):

    text = (
        email["subject"]
        + " "
        + email["body"]
    ).lower()

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

    for word in rfq_words:
        if word in text:
            return True

    return False


def extract_rfq_information(email):

    body = email["body"]
    line_items = []
    current_item = None

    for line in body.split("\n"):

        line = line.strip()

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

        elif line.lower().startswith("cas number:"):

            if current_item is not None:
                current_item["cas_number"] = (
                    line.split(":", 1)[1].strip()
                )

        elif line.lower().startswith("cas:"):

            if current_item is not None:
                current_item["cas_number"] = (
                    line.split(":", 1)[1].strip()
                )

        elif line.lower().startswith("quantity:"):

            if current_item is not None:
                current_item["quantity"] = (
                    line.split(":", 1)[1].strip()
                )

        elif line.lower().startswith("required delivery:"):

            if current_item is not None:
                current_item["delivery_date"] = (
                    line.split(":", 1)[1].strip()
                )

    if current_item is not None:
        line_items.append(current_item)

    return line_items


def find_saved_rfq(customer, product):

    rfqs = get_rfqs()

    for rfq in rfqs:

        if (
            rfq[1] == customer
            and rfq[2].lower() == product.lower()
        ):
            return rfq

    return None


if section == "Inbox / RFQ Detection":

    st.subheader("Incoming Emails")

    existing_rfqs = get_rfqs()

    for email in emails:

        already_processed = False

        for rfq in existing_rfqs:

            customer_match = (
                rfq[1] == email["customer"]
            )

            product_match = (
                rfq[2].lower()
                in email["body"].lower()
            )

            status_match = (
                rfq[6] in ["Approved", "Rejected"]
            )

            if (
                customer_match
                and product_match
                and status_match
            ):
                already_processed = True
                break

        if already_processed:
            continue

        is_rfq = detect_rfq(email)

        with st.expander(
            f"{email['subject']} — {email['sender']}"
        ):

            st.write(
                "**Sender:**",
                email["sender"]
            )

            st.write(
                "**Subject:**",
                email["subject"]
            )

            st.write("**Email:**")

            st.text(email["body"])

            st.divider()

            if not is_rfq:

                st.warning("NOT AN RFQ")

                continue

            st.success("RFQ DETECTED")

            line_items = extract_rfq_information(email)

            for item in line_items:

                product = item["product"]
                quantity_text = item["quantity"]

                try:

                    requested_quantity = float(
                        quantity_text.split()[0]
                    )

                except (ValueError, IndexError):

                    st.error(
                        f"Could not read quantity "
                        f"for {product}: "
                        f"{quantity_text}"
                    )

                    continue

                inventory_result = check_inventory(
                    product,
                    requested_quantity
                )

                st.write(
                    f"### {product}"
                )

                st.write(
                    f"Requested: "
                    f"{requested_quantity} "
                    f"{inventory_result['unit']}"
                )

                st.write(
                    f"Available: "
                    f"{inventory_result['available']} "
                    f"{inventory_result['unit']}"
                )

                if inventory_result["status"] == "Available":

                    st.success("AVAILABLE")

                    st.write(
                        f"Price: "
                        f"₹{inventory_result['price']} / "
                        f"{inventory_result['unit']}"
                    )

                    st.write(
                        f"Total: "
                        f"₹{inventory_result['total_amount']:,.2f}"
                    )

                elif inventory_result["status"] == "Insufficient":

                    st.warning("INSUFFICIENT INVENTORY")

                    st.write(
                        inventory_result["message"]
                    )

                else:

                    st.error("NOT AVAILABLE")

                    st.write(
                        inventory_result["message"]
                    )

            st.subheader("Extracted RFQ Line Items")

            for number, item in enumerate(
                line_items,
                start=1
            ):

                st.write(
                    f"### Line Item {number}"
                )

                col1, col2 = st.columns(2)

                with col1:

                    st.write(
                        "**Product:**",
                        item["product"]
                    )

                    st.write(
                        "**CAS Number:**",
                        item["cas_number"]
                    )

                with col2:

                    st.write(
                        "**Quantity:**",
                        item["quantity"]
                    )

                    st.write(
                        "**Required Delivery:**",
                        item["delivery_date"]
                    )

            st.divider()

            st.subheader(
                "Supporting Business Information"
            )

            quote_lines = []

            for item in line_items:

                inventory = find_inventory(
                    item["product"]
                )

                price = find_price(
                    item["product"]
                )

                history = find_customer_history(
                    item["customer"],
                    item["product"]
                )

                st.write(
                    f"### {item['product']}"
                )

                col1, col2, col3 = st.columns(3)

                with col1:

                    st.write("Inventory")

                    if inventory:

                        st.success(
                            f"{inventory['available_quantity']} "
                            f"{inventory['unit']} available"
                        )

                    else:

                        st.warning(
                            "Not available in-house"
                        )

                with col2:

                    st.write("Price")

                    if price:

                        st.info(
                            f"{price['currency']} "
                            f"{price['price']} / "
                            f"{price['unit']}"
                        )

                    else:

                        st.warning(
                            "No internal price"
                        )

                with col3:

                    st.write("Customer History")

                    if history:

                        st.info(
                            f"Last order: "
                            f"{history['last_quantity']} "
                            f"{item['product']}"
                        )

                        st.caption(
                            f"Last price: "
                            f"{history['last_price']}"
                        )

                    else:

                        st.info(
                            "No previous order"
                        )

                if inventory is None:

                    st.warning(
                        "Product not available in-house"
                    )

                else:

                    st.success(
                        "In-house product"
                    )

                quote_line = create_quote_line(
                    item,
                    inventory,
                    price
                )

                quote_lines.append(quote_line)

                st.divider()

            if st.button(
                "Save RFQ to CRM",
                key=f"save_{email['id']}"
            ):

                for item in line_items:
                    save_rfq(item)

                existing_rfqs = get_rfqs()

                st.success(
                    "RFQ line items saved to CRM!"
                )

            if st.button(
                "Generate Draft Quote",
                key=f"quote_{email['id']}"
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

                    inventory_result = None

                    if requested_quantity is not None:

                        inventory_result = check_inventory(
                            product,
                            requested_quantity
                        )

                    saved_rfq = find_saved_rfq(
                        customer,
                        product
                    )

                    if saved_rfq:

                        st.session_state[
                            "quote_rfq_id"
                        ] = saved_rfq[0]

                    else:

                        st.session_state[
                            "quote_rfq_id"
                        ] = None

                    st.session_state[
                        "quote_customer"
                    ] = customer

                    st.session_state[
                        "quote_product"
                    ] = product

                    st.session_state[
                        "quote_quantity"
                    ] = requested_quantity

                    st.session_state[
                        "quote_unit"
                    ] = (
                        inventory_result["unit"]
                        if inventory_result
                        else ""
                    )

                    st.session_state[
                        "quote_total"
                    ] = (
                        inventory_result["total_amount"]
                        if (
                            inventory_result
                            and inventory_result["status"]
                            == "Available"
                        )
                        else 0
                    )

                    st.session_state[
                        "quote_status"
                    ] = "Pending Review"

                st.session_state[
                    "draft_quote"
                ] = quote

                st.session_state[
                    "quote_customer"
                ] = email["customer"]

                st.success(
                    "Draft quote generated!"
                )


elif section == "RFQ Records":

    st.subheader("RFQ Records")

    rfqs = get_rfqs()

    if len(rfqs) == 0:

        st.info(
            "No RFQs have been saved yet."
        )

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
                f"RFQ #{rfq_id} — "
                f"{customer} — "
                f"{product}"
            ):

                col1, col2 = st.columns(2)

                with col1:

                    st.write(
                        "**Customer:**",
                        customer
                    )

                    st.write(
                        "**Product:**",
                        product
                    )

                    st.write(
                        "**CAS Number:**",
                        cas_number
                    )

                with col2:

                    st.write(
                        "**Quantity:**",
                        quantity
                    )

                    st.write(
                        "**Delivery:**",
                        delivery_date
                    )

                    st.write(
                        "**Status:**",
                        status
                    )

                    if (
                        total_amount is not None
                        and total_amount != 0
                    ):

                        st.write(
                            "**Total Amount:**",
                            f"₹{float(total_amount):,.2f}"
                        )


elif section == "Inventory":

    st.subheader("Company Inventory")

    inventory = get_inventory()

    if inventory:

        for item in inventory:

            st.write(
                f"**{item[1]}** | "
                f"CAS: {item[2]} | "
                f"Available: {item[3]} "
                f"{item[4]} | "
                f"Price: ₹{item[5]} / "
                f"{item[4]}"
            )

    else:

        st.info(
            "No inventory found."
        )


elif section == "Quote Review":

    st.subheader("Quote Review")

    if "draft_quote" not in st.session_state:

        st.info(
            "No draft quote has been generated yet."
        )

        st.write(
            "Go to Inbox / RFQ Detection "
            "and generate a draft quote."
        )

    else:

        st.write("### Customer")

        st.info(
            st.session_state[
                "quote_customer"
            ]
        )

        st.write("### Draft Response")

        st.text_area(
            "Review and edit the draft before approval:",
            value=st.session_state[
                "draft_quote"
            ],
            height=400,
            key="draft_quote_editor"
        )

        st.divider()

        st.warning(
            "HUMAN REVIEW REQUIRED"
        )

        current_status = st.session_state.get(
            "quote_status",
            "Pending Review"
        )

        st.write(
            f"Current status: **{current_status}**"
        )

        st.divider()

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "Approve Quote",
                key="approve_quote_button"
            ):

                rfq_id = st.session_state.get(
                    "quote_rfq_id"
                )

                customer = st.session_state.get(
                    "quote_customer"
                )

                product = st.session_state.get(
                    "quote_product"
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

                if rfq_id is None:

                    st.error(
                        "This RFQ has not been saved to CRM yet."
                    )

                    st.info(
                        "Go to Inbox / RFQ Detection, "
                        "click 'Save RFQ to CRM', "
                        "then generate the draft again."
                    )

                elif (
                    product is None
                    or quantity is None
                ):

                    st.error(
                        "Product or quantity information is missing."
                    )

                elif current_status == "Approved":

                    st.warning(
                        "This quote has already been approved."
                    )

                elif current_status == "Rejected":

                    st.warning(
                        "This quote has already been rejected."
                    )

                else:

                    current_rfqs = get_rfqs()

                    database_status = None

                    for rfq in current_rfqs:

                        if rfq[0] == rfq_id:

                            database_status = rfq[6]

                            break

                    if database_status == "Approved":

                        st.warning(
                            "This RFQ is already approved in CRM."
                        )

                        st.session_state[
                            "quote_status"
                        ] = "Approved"

                    elif database_status == "Rejected":

                        st.warning(
                            "This RFQ is already rejected in CRM."
                        )

                        st.session_state[
                            "quote_status"
                        ] = "Rejected"

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

                            st.session_state[
                                "quote_status"
                            ] = "Approved"

                            st.success(
                                "Quote approved successfully!"
                            )

                            st.success(
                                f"Inventory updated: "
                                f"{remaining} {unit} remaining."
                            )

                            st.info(
                                "This RFQ will no longer appear in Inbox."
                            )

                        else:

                            st.error(
                                f"Quote cannot be approved: {remaining}"
                            )

        with col2:

            if st.button(
                "Reject Quote",
                key="reject_quote_button"
            ):

                rfq_id = st.session_state.get(
                    "quote_rfq_id"
                )

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

                    st.session_state[
                        "quote_status"
                    ] = "Rejected"

                    st.error(
                        "Quote rejected by reviewer."
                    )

                    st.info(
                        "This RFQ will no longer appear in Inbox."
                    )
