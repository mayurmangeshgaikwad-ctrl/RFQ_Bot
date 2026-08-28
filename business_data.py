import csv


def find_inventory(product):

    with open("data/inventory.csv", "r") as file:

        reader = csv.DictReader(file)

        for row in reader:

            if row["product"].lower() == product.lower():

                return {
                    "available_quantity": row["available_quantity"],
                    "unit": row["unit"]
                }

    return None


def find_price(product):

    with open("data/pricing.csv", "r") as file:

        reader = csv.DictReader(file)

        for row in reader:

            if row["product"].lower() == product.lower():

                return {
                    "price": row["price_per_unit"],
                    "currency": row["currency"],
                    "unit": row["unit"]
                }

    return None


def find_customer_history(customer, product):

    with open("data/customer_history.csv", "r") as file:

        reader = csv.DictReader(file)

        for row in reader:

            if (
                row["customer"].lower() == customer.lower()
                and
                row["product"].lower() == product.lower()
            ):

                return {
                    "last_quantity": row["last_quantity"],
                    "last_price": row["last_price"],
                    "last_order_date": row["last_order_date"]
                }

    return None
