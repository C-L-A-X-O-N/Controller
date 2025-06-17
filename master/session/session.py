import json, websockets, logging
from master.lane import getLanes
from master.traffic_light import getTrafficLight
from master.session.registry import remove_session

class Session:
    websocket = None
    logger = None

    def __init__(self, websocket):
        self.websocket = websocket
        self.logger = logging.getLogger(__name__ + ":" + str(id(self)))

    async def init(self):
        await self.websocket.send(json.dumps({
            "type": "lanes/position",
            "data": getLanes()
        }))
        await self.websocket.send(json.dumps({
            "type": "traffic_light/position",
            "data": getTrafficLight()
        }))
        self.logger.debug("WebSocket: Initial lanes sent to client.")
        self.logger.info("WebSocket: Client Connected.")

    async def tick(self):
        message = await self.websocket.recv()

    async def send(self, message_type, data, dump_json=False):
        try:
            if dump_json:
                data = json.loads(data)
            await self.websocket.send(json.dumps({
                "type": message_type,
                "data": data
            }))
        except websockets.ConnectionClosed:
            remove_session(self)
