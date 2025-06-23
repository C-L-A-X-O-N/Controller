import json
import logging
from paho.mqtt.client import Client
import asyncio

from master.lane import setLanes
from master.state import setState
from master.traffic_light import setTrafficLight
from master.websocket_server import broadcast_websocket_message

logger = logging.getLogger(__name__)

def publish_to_websocket(loop, message_type, data, dump_json=False):
    asyncio.run_coroutine_threadsafe(
        broadcast_websocket_message(message_type, data, dump_json),
        loop
    )

SUBSCRIBER_TOPICS = {
    "claxon/lane/position": lambda client, loop, msg: setLanes(json.loads(msg), loop),
    "claxon/lane/state": lambda client, loop, msg: publish_to_websocket(loop, "lane/state", msg, True),
    "claxon/traffic_light/position": lambda client, loop, msg: setTrafficLight(json.loads(msg), loop),
    "claxon/traffic_light/state": lambda client, loop, msg: publish_to_websocket(loop, "traffic_light/state", msg, True),
    "claxon/vehicle/position": lambda client, loop, msg: publish_to_websocket(loop, "vehicle", msg, True),
    "claxon/setting/state": lambda client, loop, msg: setState(json.loads(msg), loop),
}

def setup_mqtt_client(host, port, loop = None):
    """Configuration et démarrage du client MQTT."""
    client = Client(client_id="master", clean_session=False)
    if loop is None:
        loop = asyncio.get_event_loop()
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
                SUBSCRIBER_TOPICS[topic](client, loop, msg.payload)
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