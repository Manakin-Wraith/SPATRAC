import sqlite3
import pandas as pd

def connect_to_db(db_path='spatrac.db'):
    """Connect to the SQLite database."""
    conn = sqlite3.connect(db_path)
    return conn

def fetch_products(conn):
    """Fetch all products from the database."""
    query = "SELECT * FROM products"
    return pd.read_sql_query(query, conn)

def fetch_ingredients(conn):
    """Fetch all ingredients from the database."""
    query = "SELECT * FROM ingredients"
    return pd.read_sql_query(query, conn)

def fetch_temperature_logs(conn):
    """Fetch all temperature logs from the database."""
    query = "SELECT * FROM temperature_logs"
    return pd.read_sql_query(query, conn)

def fetch_cleaning_records(conn):
    """Fetch all cleaning records from the database."""
    query = "SELECT * FROM cleaning_records"
    return pd.read_sql_query(query, conn)

def fetch_received_products(conn):
    """
    Fetch all received products from the database.
    """
    query = "SELECT * FROM received_products"
    return pd.read_sql_query(query, conn)

def display_data(df):
    """Display the DataFrame in a readable format."""
    print(df.to_string(index=False))

if __name__ == "__main__":
    conn = connect_to_db()
    print("Products:")
    display_data(fetch_products(conn))
    print("\nIngredients:")
    display_data(fetch_ingredients(conn))
    print("\nTemperature Logs:")
    display_data(fetch_temperature_logs(conn))
    print("\nCleaning Records:")
    display_data(fetch_cleaning_records(conn))
    print("\nReceived Products:")
    display_data(fetch_received_products(conn))
    conn.close()