def main(host, port):
    import paho.mqtt.client as mqtt
    import logging, time
    logger = logging.getLogger(__name__)

    topic = "demo/topic"

    client = mqtt.Client()
    client.enable_logger(logger)
    client.connect(host, port, 60)

    while True:
        message = "Hello MQTT"
        client.publish(topic, message, qos=1, retain=True)
        time.sleep(2)
