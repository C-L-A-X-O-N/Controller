import logging
import psycopg2
import threading
import asyncio
import websockets
from paho.mqtt.client import Client

# Configuration globale du logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Configuration de la base de données
DB_CONFIG = {
    "dbname": "claxon",
    "user": "user",
    "password": "password",
    "host": "localhost"
}

# Configuration MQTT
MQTT_TOPICS = {
    "lane": "controller/lane",
    "traffic_light": "controller/traffic_light",
}

connected_websockets = set()

def connect_to_database():
    """Connexion à la base de données."""
    try:
        logger.debug("Connecting to database...")
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise


def setup_mqtt_client(host, port):
    """Configuration et démarrage du client MQTT."""
    client = Client(client_id="master", clean_session=False)
    client.enable_logger(logger)

    def on_connect(client, userdata, flags, rc):
        logger.info(f"Connected to MQTT broker with result code {rc}")
        for topic in MQTT_TOPICS.values():
            client.subscribe(topic)

    def on_message(client, userdata, msg):
        try:
            def run_async_broadcast(message):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(broadcast_websocket_message(message))
                loop.close()

            # Run the broadcast in a separate thread to avoid blocking
            threading.Thread(target=run_async_broadcast, args=(f"Received data: {msg.payload.decode()}",)).start()
            if msg.topic == MQTT_TOPICS["lane"]:
                logger.info("Received lane update")
                # Traiter les données ici
            elif msg.topic == MQTT_TOPICS["traffic_light"]:
                logger.info("Received traffic light update")
                # Traiter les données ici
            else:
                logger.error(f"Unknown topic: {msg.topic}")
        except Exception as e:
            logger.error(f"Failed to process message: {e}")

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(host, port, 60)
    client.loop_start()
    return client

async def broadcast_websocket_message(message):
    disconnected = set()
    for ws in connected_websockets:
        try:
            await ws.send(message)
        except websockets.ConnectionClosed:
            disconnected.add(ws)
    connected_websockets.difference_update(disconnected)

async def handle_websocket_connection(websocket):
    """Gestion des connexions WebSocket."""
    logger.info("WebSocket: Client Connected.")
    try:
        connected_websockets.add(websocket)
        while True:
            name = await websocket.recv()
            age = await websocket.recv()

            if not name or not age:
                logger.error("Error Receiving Value from Client.")
                break

            logger.info(f"Details Received - Name: {name}, Age: {age}")
            if int(age) < 18:
                await websocket.send(f"Sorry! {name}, You can't join the club.")
            else:
                await websocket.send(f"Welcome aboard, {name}.")
    except websockets.ConnectionClosedError:
        logger.error("WebSocket: Client Disconnected.")
    finally:
        connected_websockets.remove(websocket)


async def start_websocket_server():
    """Démarrage du serveur WebSocket."""
    async with websockets.serve(handle_websocket_connection, "localhost", 7890):
        await asyncio.Future()  # run forever


def main(host, port):
    """Point d'entrée principal."""
    try:
        # Connexion à la base de données
        db_connection = connect_to_database()

        # Configuration MQTT
        mqtt_client = setup_mqtt_client(host, port)

        # Démarrage du serveur WebSocket
        asyncio.run(start_websocket_server())
    except KeyboardInterrupt:
        logger.info("Shutting down")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("MQTT client disconnected.")


if __name__ == "__main__":
    main("localhost", 1883)