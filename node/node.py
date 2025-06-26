import paho.mqtt.client as mqtt
from util.mqtt import MqttClient
import logging, json, os
import time
import signal
import sys
from .toxiproxy import ToxiproxyAPI
import random

logger = logging.getLogger(__name__)

def on_connect(client, userdata, flags, rc):
    publish_on_start("", client)

def publish_on_start(msg, client): 
    host = "toxiproxy"
    port = 3000 + int(os.environ.get("ZONE", 2))
    logger.info(f"Publishing start message to {host}:{port}")
    client.publish("traci/node/start", json.dumps({
        "host": host,
        "port": port,
        "zone": os.environ.get("ZONE", 2),
    }))


globalBroker = None

def main(host, port):
    global globalBroker
    """Main function to run the MQTT node client."""

    client = ToxiproxyAPI("http://toxiproxy:8474")

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        if globalBroker is not None:
            globalBroker.stop_paho()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    specificBroker = None
    zone = os.environ.get("ZONE", 2)

    def proxy(topic):
        def handle(message, client):
            json_message = json.loads(message)
            data = {
                "data": json_message, 
                "zone": zone
            }
            globalBroker.publish("claxon/"+topic, json.dumps(data))

        return handle
    
    logger.info(f"Starting Node in zone {zone} with host {host} and port {port}")

    TRACI_TOPICS = {
        "traci/lane/position": proxy("lane/position"),
        "traci/lane/state": proxy("lane/state"),
        "traci/traffic_light/position": proxy("traffic_light/position"),
        "traci/vehicle/position": proxy("vehicle/position"),
        "traci/traffic_light/state": proxy("traffic_light/state"),
    }
    try:
        time.sleep(5)  # Wait for the network to stabilize
        globalProxyName = "global_mqtt_node_" + zone
        try:
            proxy = client.get(globalProxyName)
            proxy.delete()
        except:
            pass 
        globalToxiproxyPort = 2000 + int(zone)
        proxy = client.create(name=globalProxyName, listen="0.0.0.0:" + str(globalToxiproxyPort), upstream=f"{host}:{port}")
        # Simule une latence aléatoire : réseau local (5-20ms) ou cloud (80-200ms)
        if os.environ.get("SIMULATE_CLOUD", "false").lower() == "true":
            latency = random.randint(80, 200)
            jitter = random.randint(10, 50)
        else:
            latency = random.randint(5, 20)
            jitter = random.randint(1, 5)
        logger.info(f"Adding latency toxic for global proxy: {latency}ms with jitter {jitter}ms")
        proxy.toxics.add(
            name="latency_in",
            type="latency",
            attributes={"latency": latency, "jitter": jitter},
            stream="downstream"
        )
        proxy.toxics.add(
            name="latency_out",
            type="latency",
            attributes={"latency": latency, "jitter": jitter},
            stream="upstream"
        )
        specificProxyName = "specific_mqtt_node_" + zone
        try:
            proxy = client.get(specificProxyName)
            proxy.delete()
        except:
            pass
        personnalBrokerHost = os.environ.get("EXTERNAL_PERSONNAL_BROKER_HOST", "controller_node")
        personnalBrokerPort = int(os.environ.get("EXTERNAL_PERSONNAL_BROKER_PORT", 1883))
        logger.info(f"Creating specific proxy for personal broker at {personnalBrokerHost}:{personnalBrokerPort}")
        proxy = client.create(name=specificProxyName, listen="0.0.0.0:" + str(3000 + int(zone)), upstream=f"{personnalBrokerHost}:{personnalBrokerPort}")
        # Simule une latence aléatoire : réseau local (5-20ms) ou cloud (80-200ms)
        if os.environ.get("SIMULATE_CLOUD", "false").lower() == "true":
            latency = random.randint(80, 200)
            jitter = random.randint(10, 50)
        else:
            latency = random.randint(5, 20)
            jitter = random.randint(1, 5)
        logger.info(f"Adding latency toxic for specific proxy: {latency}ms with jitter {jitter}ms")
        proxy.toxics.add(
            name="latency_in",
            type="latency",
            attributes={"latency": latency, "jitter": jitter},
            stream="downstream"
        )
        proxy.toxics.add(
            name="latency_out",
            type="latency",
            attributes={"latency": latency, "jitter": jitter},
            stream="upstream"
        )

        globalBroker = MqttClient(host="toxiproxy", port=globalToxiproxyPort, subscribes={
            "claxon/command/first_data": lambda message, client: globalBroker.publish("traci/first_data", "{}"),
            "traci/start": publish_on_start
        }, on_connect=on_connect)
        globalBroker.publish("traci/first_data", "")
        specificBroker = MqttClient(
            host=personnalBrokerHost,
            port=personnalBrokerPort,
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