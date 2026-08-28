# ==================================================
# CREATE ONE QUOTE LINE
# ==================================================

def create_quote_line(
    item,
    inventory,
    price
):

    product = item["product"]
    quantity = item["quantity"]
    delivery_date = item["delivery_date"]

    if inventory is not None:

        return {
            "product": product,
            "quantity": quantity,
            "delivery_date": delivery_date,
            "available": True,
            "price": price
        }

    else:

        return {
            "product": product,
            "quantity": quantity,
            "delivery_date": delivery_date,
            "available": False,
            "price": None
        }


# ==================================================
# CREATE CLIENT QUOTE
# ==================================================

def create_client_quote(
    customer,
    quote_lines
):

    quote = f"""
Dear {customer},

Thank you for your enquiry.

Please find our quotation below:

"""

    for line in quote_lines:

        quote += f"""
Product: {line['product']}
Quantity: {line['quantity']}
Required Delivery: {line['delivery_date']}
"""

        if line["available"]:

            if line["price"]:

                quote += f"""
Price: {line['price']['currency']} {line['price']['price']} per {line['price']['unit']}
"""

            quote += """
Availability: Available in our inventory.
"""

        else:

            quote += """
Availability: Not available in our inventory.
Please contact the vendor for this product.
"""

        quote += "\n"

    quote += """
Regards,
Sales Team
"""

    return quote