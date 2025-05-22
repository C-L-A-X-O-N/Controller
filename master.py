def main(host, port):
    import paho.mqtt.client as mqtt
    import logging
    logger = logging.getLogger(__name__)

    topic = "demo/topic"

    def on_connect(client, userdata, flags, rc):
        logger.info("Connected with result code "+str(rc))
        client.subscribe(topic)

    def on_message(client, userdata, msg):
        logger.debug(f"Message reçu: {msg.payload.decode()} sur le topic {msg.topic}")

    client = mqtt.Client(client_id="master", clean_session=False)
    client.enable_logger(logger)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(host, port, 60)
    client.loop_forever()