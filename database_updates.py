import sqlite3
from datetime import datetime

def update_database_schema():
    """
    Update the database schema to include new audit-related tables and fields.
    """
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()

    # Create products table with audit fields
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            final_product_batch_code TEXT NOT NULL UNIQUE,
            production_date DATE NOT NULL,
            sell_by_date DATE NOT NULL,
            use_by_date DATE,
            quantity_produced INTEGER NOT NULL,
            department TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department) REFERENCES departments(department_code)
        )
    ''')

    # Create ingredients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredient_name TEXT NOT NULL,
            supplier_name TEXT NOT NULL,
            supplier_address TEXT,
            batch_code TEXT NOT NULL,
            receiving_date DATE NOT NULL,
            country_of_origin TEXT,
            created_by TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create temperature_logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS temperature_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            temperature REAL NOT NULL,
            recorded_by TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # Create cleaning_records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cleaning_records (
            cleaning_id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            cleaning_date DATE NOT NULL,
            cleaning_type TEXT NOT NULL,
            cleaned_by TEXT NOT NULL,
            cleaning_details TEXT,
            verified_by TEXT,
            verification_date DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create product_ingredients junction table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_ingredients (
            product_id INTEGER,
            ingredient_id INTEGER,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(id),
            PRIMARY KEY (product_id, ingredient_id)
        )
    ''')

    # Add triggers for updated_at timestamp
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_product_timestamp 
        AFTER UPDATE ON products
        BEGIN
            UPDATE products SET updated_at = CURRENT_TIMESTAMP 
            WHERE id = NEW.id;
        END;
    ''')

    conn.commit()
    conn.close()

def migrate_existing_data():
    """
    Migrate existing data from received_products to the new schema.
    Handles duplicate batch codes by appending a unique identifier.
    """
    conn = sqlite3.connect('spatrac.db')
    cursor = conn.cursor()

    try:
        # Get all existing products
        cursor.execute('SELECT * FROM received_products')
        existing_products = cursor.fetchall()

        # Keep track of batch codes we've seen
        seen_batch_codes = set()

        # Migrate data to new tables
        for product in existing_products:
            batch_code = product[8]  # supplier_batch
            
            # If we've seen this batch code before, make it unique
            if batch_code in seen_batch_codes:
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                batch_code = f"{batch_code}_{timestamp}"
            
            seen_batch_codes.add(batch_code)

            try:
                # Insert into products table
                cursor.execute('''
                    INSERT INTO products (
                        product_name,
                        final_product_batch_code,
                        production_date,
                        sell_by_date,
                        quantity_produced,
                        department,
                        created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product[2],  # description as product_name
                    batch_code,  # modified batch_code
                    product[7],  # received_date as production_date
                    product[9],  # sell_by_date
                    product[3],  # quantity
                    product[5],  # department
                    product[6]   # received_by as created_by
                ))

                # If temperature log exists, migrate it
                if product[12]:  # temperature_log column
                    try:
                        temp_logs = eval(product[12])  # Assuming it's stored as a string representation of a list
                        for log in temp_logs:
                            cursor.execute('''
                                INSERT INTO temperature_logs (
                                    product_id,
                                    temperature,
                                    recorded_by,
                                    timestamp
                                ) VALUES (?, ?, ?, ?)
                            ''', (
                                cursor.lastrowid,  # product_id from the last insert
                                log['temperature'],
                                log['recorded_by'],
                                log['timestamp']
                            ))
                    except (SyntaxError, ValueError) as e:
                        continue

            except sqlite3.IntegrityError as e:
                continue

        conn.commit()

    except Exception as e:
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_database_schema()
    migrate_existing_data()
