import base64
import json
import os
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]


def _get_streamlit_secret(section, key):
    try:
        import streamlit as st
        value = st.secrets[section][key]
        return str(value)
    except Exception:
        return None


def get_gmail_service():
    credentials = None

    if os.path.exists("token.json"):
        credentials = Credentials.from_authorized_user_file(
            "token.json",
            SCOPES
        )

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        token_json = _get_streamlit_secret(
            "gmail",
            "token_json"
        )

        if token_json:
            try:
                token_info = json.loads(token_json)
                credentials = Credentials.from_authorized_user_info(
                    token_info,
                    SCOPES
                )

                if credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())

            except Exception as exc:
                raise RuntimeError(
                    "The Gmail token stored in Streamlit Secrets could not be read."
                ) from exc

    if not credentials or not credentials.valid:
        credentials_json = _get_streamlit_secret(
            "gmail",
            "credentials_json"
        )

        if credentials_json:
            try:
                client_config = json.loads(credentials_json)
            except Exception as exc:
                raise RuntimeError(
                    "The Gmail credentials stored in Streamlit Secrets are not valid JSON."
                ) from exc

            flow = InstalledAppFlow.from_client_config(
                client_config,
                SCOPES
            )

            credentials = flow.run_local_server(
                port=0
            )

        elif os.path.exists("credentials.json"):
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                SCOPES
            )

            credentials = flow.run_local_server(
                port=0
            )

        else:
            raise RuntimeError(
                "Gmail authentication is not configured. "
                "Provide credentials.json/token.json locally or configure "
                "[gmail] credentials_json and token_json in Streamlit Secrets."
            )

        if credentials:
            try:
                with open("token.json", "w") as token:
                    token.write(credentials.to_json())
            except OSError:
                pass

    return build(
        "gmail",
        "v1",
        credentials=credentials
    )


def get_header(headers, name):
    for header in headers:
        if header["name"].lower() == name.lower():
            return header["value"]
    return ""


def decode_message_data(data):
    if not data:
        return ""

    try:
        decoded = base64.urlsafe_b64decode(
            data + "=" * (-len(data) % 4)
        )
        return decoded.decode(
            "utf-8",
            errors="ignore"
        )
    except Exception:
        return ""


def get_email_body(payload):
    if not payload:
        return ""

    mime_type = payload.get(
        "mimeType",
        ""
    )

    body_data = payload.get(
        "body",
        {}
    ).get(
        "data"
    )

    if body_data and mime_type == "text/plain":
        return decode_message_data(body_data)

    parts = payload.get(
        "parts",
        []
    )

    plain_text = ""
    html_text = ""

    for part in parts:
        part_mime = part.get(
            "mimeType",
            ""
        )

        part_data = part.get(
            "body",
            {}
        ).get(
            "data"
        )

        if part_mime == "text/plain" and part_data:
            plain_text += (
                decode_message_data(part_data)
                + "\n"
            )

        elif part_mime == "text/html" and part_data:
            html_text += (
                decode_message_data(part_data)
                + "\n"
            )

        elif part_mime.startswith("multipart/"):
            nested_body = get_email_body(part)
            if nested_body:
                plain_text += nested_body + "\n"

    if plain_text.strip():
        return plain_text.strip()

    if html_text.strip():
        return clean_html(html_text)

    if body_data:
        return decode_message_data(body_data)

    return ""


def clean_html(html):
    html = re.sub(
        r"<style.*?>.*?</style>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL
    )

    html = re.sub(
        r"<script.*?>.*?</script>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL
    )

    html = re.sub(
        r"<br\s*/?>",
        "\n",
        html,
        flags=re.IGNORECASE
    )

    html = re.sub(
        r"</p>",
        "\n",
        html,
        flags=re.IGNORECASE
    )

    html = re.sub(
        r"</div>",
        "\n",
        html,
        flags=re.IGNORECASE
    )

    html = re.sub(
        r"<[^>]+>",
        " ",
        html
    )

    html = html.replace("&nbsp;", " ")
    html = html.replace("&amp;", "&")
    html = html.replace("&lt;", "<")
    html = html.replace("&gt;", ">")
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n\s*\n+", "\n\n", html)

    return html.strip()


def get_latest_emails(max_results=10):
    service = get_gmail_service()

    results = service.users().messages().list(
        userId="me",
        maxResults=max_results
    ).execute()

    messages = results.get(
        "messages",
        []
    )

    emails = []

    for message in messages:
        message_data = service.users().messages().get(
            userId="me",
            id=message["id"],
            format="full"
        ).execute()

        payload = message_data.get(
            "payload",
            {}
        )

        headers = payload.get(
            "headers",
            []
        )

        sender = get_header(headers, "From")
        subject = get_header(headers, "Subject")
        date = get_header(headers, "Date")
        body = get_email_body(payload)

        emails.append(
            {
                "id": message["id"],
                "sender": sender,
                "subject": subject,
                "date": date,
                "body": body
            }
        )

    return emails


def detect_rfq(email):
    subject = email.get(
        "subject",
        ""
    ).lower().strip()

    body = email.get(
        "body",
        ""
    ).lower().strip()

    if re.search(r"\brfq\b", subject):
        return True

    strong_phrases = [
        "request for quotation",
        "request for quote",
        "quotation request",
        "please provide a quotation",
        "please provide your quotation",
        "please provide your best price",
        "commercial offer"
    ]

    for phrase in strong_phrases:
        if phrase in subject or phrase in body:
            return True

    has_product = bool(
        re.search(
            r"\bproduct\s*:",
            body
        )
    )

    has_quantity = bool(
        re.search(
            r"\bquantity\s*:",
            body
        )
    )

    has_cas = bool(
        re.search(
            r"\bcas(?:\s+number)?\s*:",
            body
        )
    )

    has_delivery = bool(
        re.search(
            r"\brequired\s+delivery\s*:",
            body
        )
    )

    if has_product and has_quantity:
        return True

    if has_product and has_cas and has_quantity:
        return True

    if has_product and has_quantity and has_delivery:
        return True

    return False


def extract_rfq_information(email):
    body = email.get(
        "body",
        ""
    )

    subject = email.get(
        "subject",
        ""
    )

    customer = extract_customer_name(
        email.get(
            "sender",
            ""
        )
    )

    line_items = []
    current_item = None

    for line in body.splitlines():
        line = line.strip()

        if not line:
            continue

        product_match = re.match(
            r"^product\s*:\s*(.+)$",
            line,
            flags=re.IGNORECASE
        )

        if product_match:
            if current_item is not None:
                line_items.append(current_item)

            current_item = {
                "customer": customer,
                "product": product_match.group(1).strip(),
                "cas_number": "Unknown",
                "quantity": "Unknown",
                "delivery_date": "Unknown"
            }
            continue

        if current_item is None:
            continue

        cas_match = re.match(
            r"^cas(?:\s+number)?\s*:\s*(.+)$",
            line,
            flags=re.IGNORECASE
        )

        if cas_match:
            current_item["cas_number"] = cas_match.group(1).strip()
            continue

        quantity_match = re.match(
            r"^quantity\s*:\s*(.+)$",
            line,
            flags=re.IGNORECASE
        )

        if quantity_match:
            current_item["quantity"] = quantity_match.group(1).strip()
            continue

        delivery_match = re.match(
            r"^required\s+delivery\s*:\s*(.+)$",
            line,
            flags=re.IGNORECASE
        )

        if delivery_match:
            current_item["delivery_date"] = delivery_match.group(1).strip()
            continue

    if current_item is not None:
        line_items.append(current_item)

    if not line_items:
        subject_match = re.search(
            r"rfq\s*[-:]\s*(.+?)\s*[-:]\s*(\d+(?:\.\d+)?)\s*(kg|kgs|g|litre|liter|litres|l)",
            subject,
            flags=re.IGNORECASE
        )

        if subject_match:
            line_items.append(
                {
                    "customer": customer,
                    "product": subject_match.group(1).strip(),
                    "cas_number": "Unknown",
                    "quantity": (
                        subject_match.group(2)
                        + " "
                        + subject_match.group(3).upper()
                    ),
                    "delivery_date": "Unknown"
                }
            )

    return line_items


def extract_customer_name(sender):
    if not sender:
        return "Unknown Customer"

    match = re.match(
        r"^\s*(.*?)\s*<[^>]+>\s*$",
        sender
    )

    if match:
        name = match.group(1).strip()
        if name:
            return name

    email_match = re.search(
        r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        sender
    )

    if email_match:
        email_address = email_match.group(0)
        username = email_address.split("@")[0]

        return username.replace(".", " ").replace("_", " ").title()

    return sender


def main():
    print()
    print("Gmail RFQ Reader")
    print("=" * 50)

    emails = get_latest_emails(
        max_results=10
    )

    print(
        f"Found {len(emails)} emails."
    )

    print()

    rfq_count = 0

    for number, email in enumerate(
        emails,
        start=1
    ):
        is_rfq = detect_rfq(email)

        if is_rfq:
            rfq_count += 1

        print(
            f"EMAIL {number}"
        )

        print(
            "From:",
            email["sender"]
        )

        print(
            "Subject:",
            email["subject"]
        )

        print(
            "Date:",
            email["date"]
        )

        print(
            "RFQ:",
            "YES" if is_rfq else "NO"
        )

        if is_rfq:
            extracted_items = extract_rfq_information(email)

            print(
                "Extracted RFQ:"
            )

            for item in extracted_items:
                print(
                    f"  Product: {item['product']}"
                )

                print(
                    f"  CAS: {item['cas_number']}"
                )

                print(
                    f"  Quantity: {item['quantity']}"
                )

                print(
                    f"  Delivery: {item['delivery_date']}"
                )

        print(
            "Body:"
        )

        print(
            email["body"][:1000]
        )

        print(
            "-" * 50
        )

    print()
    print(
        f"RFQs detected: {rfq_count}"
    )


if __name__ == "__main__":
    main()
