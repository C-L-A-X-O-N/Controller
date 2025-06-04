import paho.mqtt.client as mqtt
import logging
import time
import signal
import sys

logger = logging.getLogger(__name__)

def proxy(topic):
    def handle(client, message):
        client.publish("claxon/"+topic, message)

    return handle

TRACI_TOPICS = {
    "traci/lane/position": proxy("lane/position"),
    "traci/lane/state": proxy("lane/state"),
    "traci/traffic_light/position": proxy("traffic_light/position"),
    "traci/vehicle/position": proxy("vehicle/position"),
    "traci/traffic_light/state": proxy("traffic_light/state"),
    "claxon/command/get_init": lambda client, message: client.publish("controller/command/get_init", ""),
}

def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the broker."""
    logger.info(f"Connected to MQTT broker with result code {rc}")

    for topic in TRACI_TOPICS.keys():
        client.subscribe(topic)
        logger.info(f"Subscribed to topic {topic}")

    logger.info("Requesting initial data from traci")
    client.publish("controller/command/get_init", "")


def on_disconnect(client, userdata, rc):
    """Callback for when the client disconnects from the broker."""
    if rc != 0:
        logger.warning(f"Unexpected disconnection with code {rc}")
    else:
        logger.info("Disconnected from MQTT broker")

def on_message(client, userdata, msg):
    """Callback for when a message is received from the broker."""
    logger.debug(f"Received message on topic {msg.topic}")
    if msg.topic in TRACI_TOPICS.keys():
        try:
            TRACI_TOPICS[msg.topic](client, msg.payload)
        except Exception as e:
            logger.error(f"Error handling message on topic {msg.topic}: {e}")
    else:
        logger.warning(f"No handler for topic {msg.topic}")

def main(host, port):
    """Main function to run the MQTT node client."""

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        client.loop_stop()
        client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    client = mqtt.Client()
    client.enable_logger(logger)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    try:
        client.connect(host, port, 60)
        client.loop_start()

        # Main loop
        while True:
            time.sleep(0.1)

    except Exception as e:
        logger.error(f"Error in MQTT node: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        logger.info("MQTT client disconnected")