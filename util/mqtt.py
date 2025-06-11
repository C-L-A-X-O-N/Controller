import json, logging
import paho.mqtt.client as mqtt


class MqttClient:
    client = None
    logger = None
    host = None
    port = None
    subscribes = {}
    _on_connect = None
    _on_message = None

    def __init__(self, host, port, subscribes=None, on_connect=None, on_message=None):
        self.host = host
        self.port = port
        self.client = mqtt.Client()
        self.logger = logging.getLogger(__name__ + ":" + host + ":" + str(port))
        self.subscribes = subscribes or {}
        self._on_connect = on_connect
        self._on_message = on_message
        self.run_paho()
        

    def run_paho(self):
        try:
            self.logger.info(f"Connecting to MQTT broker at {self.host}:{self.port}")
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            self.client.enable_logger(self.logger)
            self.client.loop_start()
        except KeyboardInterrupt:
            self.stop_paho()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.info("Connected to MQTT broker successfully")
            for topic in self.subscribes.keys():
                self.logger.info("Subscribed to topic " + topic)
                client.subscribe(topic)
        else:
            self.logger.error(f"Failed to connect to MQTT broker, return code {rc}")
        if self._on_connect:
            self._on_connect(client, userdata, flags, rc)


    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        self.logger.debug(f"Received message on topic {topic}")

        for t, func in self.subscribes.items():
            if topic == t:
                func(payload, self)
        if self._on_message:
            self._on_message(client, userdata, msg)
    
    def stop_paho(self):
        self.logger.info("Stopping MQTT client...")
        self.client.publish("traci/node/stop", "")
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topic, payload):
        self.client.publish(topic, payload)