import logging
import asyncio
from .database import setup_database
from .handler import setup_handler
from .mqtt_client import setup_mqtt_client, close_mqtt_client
from .websocket_server import start_websocket_server

logger = logging.getLogger(__name__)

def main(host, port):
    """Point d'entrée principal."""
    mqtt_client = None
    try:
        logger.info("Starting Claxon Master Controller...")
        setup_database()
        setup_handler()

        # Configuration MQTT
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        mqtt_client = setup_mqtt_client(host, port, loop)

        loop.run_until_complete(start_websocket_server())
    except KeyboardInterrupt:
        logger.info("Shutting down")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if mqtt_client != None:
            close_mqtt_client(mqtt_client)