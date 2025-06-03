import json
import logging
from paho.mqtt.client import Client
import asyncio

from master.lane import setLanes
from master.traffic_light import setTrafficLight
from master.websocket_server import broadcast_websocket_message

logger = logging.getLogger(__name__)

SUBSCRIBER_TOPICS = {
    "claxon/lane/position": lambda client, msg: setLanes(json.loads(msg)),
    "claxon/traffic_light/position": lambda client, msg: setTrafficLight(json.loads(msg)),
    "claxon/traffic_light/state": lambda client, msg: asyncio.run(broadcast_websocket_message("traffic_light/state", json.loads(msg))),
    "claxon/vehicle/position": lambda client, msg: asyncio.run(broadcast_websocket_message("vehicle", json.loads(msg))),
}

def setup_mqtt_client(host, port):
    """Configuration et démarrage du client MQTT."""
    client = Client(client_id="master", clean_session=False)
    client.enable_logger(logger)

    def on_connect(client, userdata, flags, rc):
        logger.info(f"Connected to MQTT broker with result code {rc}")
        for topic in SUBSCRIBER_TOPICS.keys():
            client.subscribe(topic)

        client.publish("claxon/command/get_init", "")

    def on_message(client, userdata, msg):
        logger.info(f"Received message on topic {msg.topic}")
        handled = False
        for topic in SUBSCRIBER_TOPICS.keys():
            if msg.topic == topic:
                SUBSCRIBER_TOPICS[topic](client, msg.payload)
                handled = True

        if not handled:
            logger.warning(f"No handler for topic {msg.topic}")


    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(host, port, 60)
    client.loop_start()
    return client

def close_mqtt_client(client):
    """Arrête le client MQTT."""
    client.loop_stop()
    client.disconnect()
    logger.info("MQTT client disconnected.")