import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            database=os.getenv("DB_NAME", "sistema_inventario_db"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "root"),
            # Aiven requires SSL, so we enable it. 
            # In a production setup, a CA certificate is recommended, but this works for basic connectivity.
            ssl_disabled=False
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None
