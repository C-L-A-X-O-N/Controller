import logging, os
import psycopg2

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME", "claxon"),
    "user": os.environ.get("DB_USER", "user"),
    "password": os.environ.get("DB_PASSWORD", "password"),
    "host": os.environ.get("DB_HOST", "localhost"),
    "async_": False
}

def connect_to_database():
    """Connexion à la base de données."""
    logger.debug("Attempting to connect to the database with config: %s", DB_CONFIG)
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

def setup_database():
    """Initialisation de la base de données."""
    try:
        connection = connect_to_database()
        cursor = connection.cursor()
        logger.debug("Creating tables if they do not exist...")
        
        # Création des tables si elles n'existent pas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id VARCHAR(50) PRIMARY KEY,
                geom GEOMETRY(Point, 4326),
                type VARCHAR(50),
                angle FLOAT,
                speed FLOAT,
                accident BOOLEAN DEFAULT FALSE
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lanes (
                id VARCHAR(255) PRIMARY KEY,
                geom GEOMETRY(MultiLineString, 4326),
                priority INTEGER,
                type VARCHAR(255),
                jam FLOAT NOT NULL DEFAULT 0.0
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS traffic_lights (
                id VARCHAR PRIMARY KEY,
                geom geometry(Point, 4326) NOT NULL,
                in_lane VARCHAR,
                out_lane VARCHAR,
                via_lane VARCHAR,
                state VARCHAR(255) NOT NULL DEFAULT '',
            )            
        """)
        
        connection.commit()
        logger.info("Database setup completed successfully.")
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
    finally:
        close_database_connection(connection)