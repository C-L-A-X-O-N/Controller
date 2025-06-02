import logging
import psycopg2

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "dbname": "claxon",
    "user": "user",
    "password": "password",
    "host": "localhost"
}

def connect_to_database():
    """Connexion à la base de données."""
    try:
        logger.debug("Connecting to database...")
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

def close_database_connection(connection):
    """Fermeture de la connexion à la base de données."""
    if connection:
        connection.close()
        logger.debug("Database connection closed.")