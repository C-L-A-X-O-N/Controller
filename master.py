from traci import switch


def main(host, port):
    import paho.mqtt.client as mqtt
    import logging, json, psycopg2
    logger = logging.getLogger(__name__)

    controller_lane_topic = "controller/lane"
    controller_traffic_light_topic = "controller/traffic_light"

    logging.debug("Connecting to database...")
    db = psycopg2.connect(
        dbname="claxon",
        user="user",
        password="password",
        host="localhost"
    )

    def on_connect(client, userdata, flags, rc):
        logger.info("Connected with result code "+str(rc))
        client.subscribe(controller_lane_topic)
        client.subscribe(controller_traffic_light_topic)

    def on_message(client, userdata, msg):
        if msg.topic == controller_lane_topic:
            logger.info("Received lane update")
            try:
                data = json.loads(msg.payload.decode())
            except Exception as e:
                logger.error("Failed to process traffic light update: " + str(e))
        elif msg.topic == controller_traffic_light_topic:
            logger.info("Received traffic light update")
            try:
                data = json.loads(msg.payload.decode())
            except Exception as e:
                logger.error("Failed to process traffic light update: " + str(e))
        else:
            logger.error("Topic inconnu: " + msg.topic)

    client = mqtt.Client(client_id="master", clean_session=False)
    client.enable_logger(logger)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(host, port, 60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")