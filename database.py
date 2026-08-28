import sqlite3


DATABASE_NAME = "rfq_bot.db"


def create_database():

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.cursor()

    # ==========================================
    # RFQ TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rfqs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            customer TEXT,

            product TEXT,

            cas_number TEXT,

            quantity TEXT,

            delivery_date TEXT,

            status TEXT,

            total_amount REAL DEFAULT 0

        )
    """)


    # ==========================================
    # INVENTORY TABLE
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            product TEXT UNIQUE,

            cas_number TEXT,

            available_quantity REAL,

            unit TEXT,

            price REAL,

            currency TEXT

        )
    """)


    # ==========================================
    # INVENTORY TRANSACTIONS
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_transactions (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            product TEXT,

            quantity_given REAL,

            inventory_before REAL,

            inventory_after REAL,

            customer TEXT,

            rfq_id INTEGER,

            transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)


    # ==========================================
    # SENT QUOTES
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_quotes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            customer TEXT,

            product TEXT,

            quantity REAL,

            total_amount REAL,

            status TEXT,

            sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)


    connection.commit()

    connection.close()


# ==================================================
# SAVE RFQ
# ==================================================

def save_rfq(rfq):

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO rfqs
        (
            customer,
            product,
            cas_number,
            quantity,
            delivery_date,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (

        rfq["customer"],
        rfq["product"],
        rfq["cas_number"],
        rfq["quantity"],
        rfq["delivery_date"],
        "Pending Review"

    ))

    connection.commit()

    connection.close()


# ==================================================
# GET RFQs
# ==================================================

def get_rfqs():

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            customer,
            product,
            cas_number,
            quantity,
            delivery_date,
            status,
            total_amount
        FROM rfqs
        ORDER BY id DESC
    """)

    rfqs = cursor.fetchall()

    connection.close()

    return rfqs


# ==================================================
# ADD INVENTORY
# ==================================================

def add_inventory(
    product,
    cas_number,
    available_quantity,
    unit,
    price,
    currency="INR"
):

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO inventory
        (
            product,
            cas_number,
            available_quantity,
            unit,
            price,
            currency
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (

        product,
        cas_number,
        available_quantity,
        unit,
        price,
        currency

    ))

    connection.commit()

    connection.close()


# ==================================================
# GET INVENTORY
# ==================================================

def get_inventory():

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            product,
            cas_number,
            available_quantity,
            unit,
            price,
            currency
        FROM inventory
        ORDER BY product
    """)

    inventory = cursor.fetchall()

    connection.close()

    return inventory


# ==================================================
# GET ONE PRODUCT
# ==================================================

def get_inventory_product(product):

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            product,
            cas_number,
            available_quantity,
            unit,
            price,
            currency
        FROM inventory
        WHERE LOWER(product) = LOWER(?)
    """, (product,))

    item = cursor.fetchone()

    connection.close()

    return item


# ==================================================
# REDUCE INVENTORY
# ==================================================

def reduce_inventory(
    product,
    quantity_given,
    customer,
    rfq_id
):

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.cursor()

    # Find current inventory

    cursor.execute("""
        SELECT available_quantity
        FROM inventory
        WHERE LOWER(product) = LOWER(?)
    """, (product,))

    result = cursor.fetchone()


    if result is None:

        connection.close()

        return False, "Product not found in inventory."


    current_quantity = float(result[0])

    quantity_given = float(quantity_given)


    # Check sufficient stock

    if quantity_given > current_quantity:

        connection.close()

        return False, "Insufficient inventory."


    # Calculate remaining inventory

    remaining_quantity = (
        current_quantity - quantity_given
    )


    # Update inventory

    cursor.execute("""
        UPDATE inventory

        SET available_quantity = ?

        WHERE LOWER(product) = LOWER(?)
    """, (

        remaining_quantity,
        product

    ))


    # Record transaction

    cursor.execute("""
        INSERT INTO inventory_transactions
        (
            product,
            quantity_given,
            inventory_before,
            inventory_after,
            customer,
            rfq_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (

        product,
        quantity_given,
        current_quantity,
        remaining_quantity,
        customer,
        rfq_id

    ))


    connection.commit()

    connection.close()


    return True, remaining_quantity


# ==================================================
# UPDATE RFQ STATUS
# ==================================================

def update_rfq_status(
    rfq_id,
    status,
    total_amount=0
):

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.cursor()

    cursor.execute("""
        UPDATE rfqs

        SET
            status = ?,
            total_amount = ?

        WHERE id = ?
    """, (

        status,
        total_amount,
        rfq_id

    ))

    connection.commit()

    connection.close()


# ==================================================
# SAVE SENT QUOTE
# ==================================================

def save_sent_quote(
    customer,
    product,
    quantity,
    total_amount
):

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO sent_quotes
        (
            customer,
            product,
            quantity,
            total_amount,
            status
        )
        VALUES (?, ?, ?, ?, ?)
    """, (

        customer,
        product,
        quantity,
        total_amount,
        "Sent"

    ))

    connection.commit()

    connection.close()


# ==================================================
# GET SENT QUOTES
# ==================================================

def get_sent_quotes():

    connection = sqlite3.connect(DATABASE_NAME)

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            customer,
            product,
            quantity,
            total_amount,
            status,
            sent_date

        FROM sent_quotes

        ORDER BY id DESC
    """)

    quotes = cursor.fetchall()

    connection.close()

    return quotes