import paho.mqtt.client as mqtt
import logging
import time
import signal
import sys

logger = logging.getLogger(__name__)


def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the broker."""
    logger.info(f"Connected to MQTT broker with result code {rc}")


def on_disconnect(client, userdata, rc):
    """Callback for when the client disconnects from the broker."""
    if rc != 0:
        logger.warning(f"Unexpected disconnection with code {rc}")
    else:
        logger.info("Disconnected from MQTT broker")


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

    # MQTT configuration
    topic = "demo/topic"

    # Setup MQTT client
    client = mqtt.Client()
    client.enable_logger(logger)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    try:
        client.connect(host, port, 60)
        client.loop_start()

        # Main loop
        while True:
            message = "Hello MQTT"
            client.publish(topic, message, qos=1, retain=True)
            logger.debug(f"Published message: {message}")
            time.sleep(2)

    except Exception as e:
        logger.error(f"Error in MQTT node: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        logger.info("MQTT client disconnected")