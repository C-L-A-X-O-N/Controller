import paho.mqtt.client as mqtt
from util.mqtt import MqttClient
import logging, json, os
import time
import signal
import sys

logger = logging.getLogger(__name__)

import math

def distance(coord1, coord2):
    # coordonnées (lat, lon) en degrés
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    R = 6371000  # Rayon de la Terre en mètres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

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

vehicle_buffer = {}

def process_vehicle_positions(vehicles):
    for v in vehicles:
        vehicle_buffer[v["id"]] = v

traffic_lights = {}

def process_traffic_light_positions(lights):
    for light in lights:
        traffic_lights[light["id"]] = {
            "position": light["position"],
            "in_lane": light["in_lane"]
        }

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
            if topic == "vehicle/position":
                process_vehicle_positions(json_message)
            elif topic == "traffic_light/position":
                process_traffic_light_positions(json_message)
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

        def detect_emergency_and_request_tls():
            for v in vehicle_buffer.values():
                logger.info(f"🛻 Vérif du véhicule {v['id']} type: {v['type']}")
                if "emergency" not in v["type"]:
                    continue
                v_pos = v["position"]
                v_id = v["id"]
                closest_tls = None
                min_dist = float("inf")

                for tls_id, tls in traffic_lights.items():
                    tls_pos = tls["position"]
                    
                    dist = distance(v_pos, tls_pos)
                    logger.info(f" Dist {v_id} → {tls_id}: {dist:.1f}m")
                    if dist < min_dist and dist < 50:
                        logger.info(f"{tls_id} est le plus proche ({min_dist:.1f}m)")
                        min_dist = dist
                        closest_tls = tls_id

                if closest_tls:
                    logger.info(f" {v_id} proche de {closest_tls} ({min_dist:.1f}m) → demande de vert")
                    globalBroker.publish("claxon/command/traffic_light/next_phase", json.dumps({
                        "id": closest_tls
                    }))

        # Main loop
        while True:
            detect_emergency_and_request_tls()
            time.sleep(0.01)

    except Exception as e:
        logger.error(f"Error in MQTT node: {e}")
    finally:
        logger.info("Stopping MQTT clients...")
        if globalBroker is not None:
            globalBroker.stop_paho()
        if specificBroker is not None:
            specificBroker.stop_paho()