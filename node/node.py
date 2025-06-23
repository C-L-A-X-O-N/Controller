import paho.mqtt.client as mqtt
from util.mqtt import MqttClient
import logging, json, os
import time
import signal
import sys

logger = logging.getLogger(__name__)

def on_connect(client, userdata, flags, rc):
    publish_on_start("", client)

def publish_on_start(msg, client): 
    host = os.environ.get("EXTERNAL_PERSONNAL_BROKER_HOST", "controller_node")
    port = int(os.environ.get("EXTERNAL_PERSONNAL_BROKER_PORT", 1883))
    logger.info(f"Publishing start message to {host}:{port}")
    client.publish("traci/node/start", json.dumps({
        "host": host,
        "port": port,
        "zone": os.environ.get("ZONE", 2),
    }))

def main(host, port):
    """Main function to run the MQTT node client."""

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        if globalBroker is not None:
            globalBroker.stop_paho()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    globalBroker = None
    specificBroker = None

    def proxy(topic):
        def handle(message, client):
            json_message = json.loads(message)
            data = {
                "data": json_message, 
                "zone": os.environ.get("ZONE", 2)
            }
            globalBroker.publish("claxon/"+topic, json.dumps(data))

        return handle
    
    logger.info(f"Starting Node in zone {os.environ.get('ZONE', 2)} with host {host} and port {port}")

    TRACI_TOPICS = {
        "traci/lane/position": proxy("lane/position"),
        "traci/lane/state": proxy("lane/state"),
        "traci/traffic_light/position": proxy("traffic_light/position"),
        "traci/vehicle/position": proxy("vehicle/position"),
        "traci/traffic_light/state": proxy("traffic_light/state"),
    }
    try:
        time.sleep(5)  # Wait for the network to stabilize
        globalBroker = MqttClient(host=host, port=port, subscribes={
            "claxon/command/first_data": lambda message, client: globalBroker.publish("traci/first_data", "{}"),
            "traci/start": publish_on_start
        }, on_connect=on_connect)
        specificBroker = MqttClient(
            host=os.environ.get("PERSONNAL_BROKER_HOST", "localhost"),
            port=int(os.environ.get("PERSONNAL_BROKER_PORT", 1883)),
            subscribes=TRACI_TOPICS
        )

        # Main loop
        while True:
            time.sleep(0.01)

    except Exception as e:
        logger.error(f"Error in MQTT node: {e}")
    finally:
        logger.info("Stopping MQTT clients...")
        if globalBroker is not None:
            globalBroker.stop_paho()
        if specificBroker is not None:
            specificBroker.stop_paho()