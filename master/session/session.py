import json, websockets, logging, asyncio
from master.lane import getLanes
from master.traffic_light import getTrafficLight
from master.session.registry import remove_session
from master.vehicle import getVehiclesIn, getVehicles

class Session:
    websocket = None
    logger = None
    minPos = [None, None]
    maxPos = [None, None]

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
        data = json.loads(message)
        if "type" not in data or "data" not in data:
            self.logger.error("WebSocket: Invalid message format received.")
            return
        
        if data["type"] == "session/frame_update":
            if "minX" in data["data"] and "minY" in data["data"] and "maxX" in data["data"] and "maxY" in data["data"]:
                self.set_frame(data["data"]["minX"], data["data"]["minY"], data["data"]["maxX"], data["data"]["maxY"])
            else:
                self.logger.error("WebSocket: Frame update message missing required fields.")

    async def send(self, message_type, data, dump_json=False):
        try:
            if dump_json:
                data = json.loads(data)
            await self.websocket.send(json.dumps({
                "type": message_type,
                "data": data
            }))
        except websockets.ConnectionClosed:
            self.logger.warning("WebSocket: Connection closed while trying to send message.")
            remove_session(self)

    def set_frame(self, minX, minY, maxX, maxY):
        self.minPos = [minX, minY]
        self.maxPos = [maxX, maxY]
        self.logger.debug(f"WebSocket: Frame set to {self.minPos} - {self.maxPos}")

    def trigger_vehicle_update(self, loop):
        """Trigger an update for the vehicles in this session."""
        try:
            self.logger.debug("WebSocket: Triggering vehicle update.")
            vehicles = []
            if self.minPos[0] is not None and self.maxPos[0] is not None:
                vehicles = getVehiclesIn(self.minPos[0], self.minPos[1], self.maxPos[0], self.maxPos[1])
            else:
                vehicles = getVehicles()
            asyncio.run_coroutine_threadsafe(
                self.send("vehicle", vehicles, False),
                loop
            )
        except Exception as e:
            self.logger.error(f"WebSocket: Failed to send vehicles update: {e}")
            remove_session(self)
        
    def trigger_lane_update(self, loop, updatedData):
        """Trigger an update for the lanes in this session."""
        try:
            self.logger.debug(f"WebSocket: Triggering lane update (frame: {self.minPos} - {self.maxPos})")
            dataToSend = []
            for lane in updatedData:
                if self.minPos[0] is not None and self.maxPos[0] is not None:
                    # lane[shape] is a list of points [[long, lat], ...]
                    shape = lane['shape']
                    del lane['shape']
                    if not shape or len(shape) < 2:
                        dataToSend.append(lane)
                        continue

                    # Check if the lane is within the frame
                    minX, minY = self.minPos
                    maxX, maxY = self.maxPos
                    if maxX < minX:
                        minX, maxX = maxX, minX
                    if maxY < minY:
                        minY, maxY = maxY, minY
                    if any(minX <= pt[0] <= maxX and minY <= pt[1] <= maxY for pt in shape):
                        dataToSend.append(lane)
            asyncio.run_coroutine_threadsafe(
                self.send("lane/state", dataToSend, False),
                loop
            )
        except Exception as e:
            self.logger.error(f"WebSocket: Failed to send lanes update: {e}")
            remove_session(self)