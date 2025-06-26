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

db = None

def connect_to_database():
    global db
    """Connexion à la base de données."""
    
    # Check if connection is closed or None and reconnect if needed
    if db is None or db.closed:
        logger.debug("Attempting to connect to the database with config: %s", DB_CONFIG)
        try:
            logger.info("Connecting to database...")
            db = psycopg2.connect(**DB_CONFIG)
            db.autocommit = True
            logger.info("Database connection established successfully.")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
    else:
        logger.debug("Using existing database connection.")
        
    # Test the connection to ensure it's still active
    try:
        with db.cursor() as test_cursor:
            test_cursor.execute("SELECT 1")
    except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
        logger.warning(f"Database connection test failed: {e}. Reconnecting...")
        try:
            db = psycopg2.connect(**DB_CONFIG)
            db.autocommit = True
            logger.info("Database reconnection successful.")
        except Exception as e:
            logger.error(f"Database reconnection failed: {e}")
            
    return db

def setup_database():
    """Initialisation de la base de données."""
    global db
    db = connect_to_database()
    return db

def get_active_connection():
    """Returns an active database connection, reconnecting if necessary."""
    global db
    # Force a reconnection if the connection is closed or None
    if db is None or db.closed:
        db = connect_to_database()
    
    # Test the connection
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT 1")
    except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
        logger.warning(f"Inactive database connection: {e}. Reconnecting...")
        db = connect_to_database()
    
    return db

def setup_database():
    """Initialisation de la base de données."""
    try:
        connection = connect_to_database()
        cursor = connection.cursor()
        logger.info("Creating tables if they do not exist...")
        
        # Création des tables si elles n'existent pas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id VARCHAR(50) PRIMARY KEY,
                geom GEOMETRY(Point, 4326),
                type VARCHAR(50),
                angle FLOAT,
                speed FLOAT,
                zone INTEGER DEFAULT 0,
                accident BOOLEAN DEFAULT FALSE
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lanes (
                id VARCHAR(255) PRIMARY KEY,
                geom GEOMETRY(MultiLineString, 4326),
                priority INTEGER,
                type VARCHAR(255),
                zone INTEGER DEFAULT 0,
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
                zone INTEGER DEFAULT 0,
                state VARCHAR(255) NOT NULL DEFAULT ''
            )            
        """)

        cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS accidents (
                    vehicle_id TEXT PRIMARY KEY,
                    geom GEOMETRY(Point, 4326),
                    type TEXT,
                    start_time INTEGER,
                    zone INTEGER,
                    duration INTEGER DEFAULT 10,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        
        connection.commit()
        logger.info("Database setup completed successfully.")
    except Exception as e:
        logger.error(f"Database setup failed: {e}")