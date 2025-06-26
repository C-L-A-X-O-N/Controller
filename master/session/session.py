import json, websockets, logging, asyncio
from master.lane import getLanes, getLanesIn
from master.traffic_light import getTrafficLight, getTrafficLightIn
from master.session.registry import remove_session
from master.vehicle import getVehiclesIn, getVehicles

class Session:
    websocket = None
    logger = None
    minPos = [None, None]
    maxPos = [None, None]
    focused = False

    def __init__(self, websocket):
        self.websocket = websocket
        self.logger = logging.getLogger(__name__ + ":" + str(id(self)))

    async def init(self):
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
                await self.websocket.send(json.dumps({
                    "type": "lanes/position",
                    "data": getLanesIn(data["data"]["minX"], data["data"]["minY"], data["data"]["maxX"], data["data"]["maxY"])
                }))
            else:
                self.logger.error("WebSocket: Frame update message missing required fields.")
        elif data["type"] == "session/focus":
            self.focused = data["data"].get("focused", False)
            self.logger.debug(f"WebSocket: Focus set to {self.focused}.")
        elif data["type"] == "session/update_vehicles":
            loop = asyncio.get_event_loop()
            self.trigger_vehicle_update(loop)
        elif data["type"] == "session/update_lights":
            loop = asyncio.get_event_loop()
            self.trigger_lights_update(loop)
        elif data["type"] == "command/traffic_light/update":
            light_id = data["data"].get("id")
            new_state = data["data"].get("state")

            if light_id is not None and new_state is not None:

                from master.traffic_light import get_traffic_light_by_id
                from master.mqtt_client import mqtt_publish_traffic_light_state
                current_light = get_traffic_light_by_id(light_id)
                
                if current_light is None:
                    self.logger.warning(f"Traffic light {light_id} not found in DB.")
                    return
                
                current_state = current_light.get("state")

                def to_numeric_state(val):
                    if isinstance(val, int):
                        return val
                    if val in ("G", "g"):
                        return 0
                    elif val in ("Y", "y", "O", "o"):
                        return 1
                    elif val in ("R", "r"):
                        return 2
                    return 3
                
                if to_numeric_state(current_state) == to_numeric_state(new_state):
                    self.logger.info(f"No update needed for light {light_id}, state unchanged.")
                    return
                self.logger.info(f"Updated traffic light state via MQTT current: {current_light}")
                self.logger.info(f"Updated traffic light state via MQTT newlight : {new_state}")
 
                payload = {
                    "id": light_id,
                    "state": new_state
                }
                mqtt_publish_traffic_light_state(payload)

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
        if not self.focused:
            self.logger.debug("WebSocket: Session not focused, skipping vehicle update.")
            return
        try:
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
        if not self.focused:
            # self.logger.warning("WebSocket: Session not focused, skipping lane update.")
            return
        try:
            dataToSend = []
            for lane in updatedData:
                if self.minPos[0] is not None and self.maxPos[0] is not None and "shape" in lane:
                    # lane[shape] is a list of points [[long, lat], ...]
                    shape = lane['shape']
                    del lane['shape']
                    if self.shape_bb_frame(shape):
                        dataToSend.append(lane)
            asyncio.run_coroutine_threadsafe(
                self.send("lane/state", dataToSend, False),
                loop
            )
        except Exception as e:
            self.logger.error(f"WebSocket: Failed to send lanes update: {e}")
            remove_session(self)

    def trigger_lane_position(self, loop):
        """Trigger an update for the lanes position in this session."""
        try:
            asyncio.run_coroutine_threadsafe(
                self.send("lane/position", getLanesIn(self.minPos[0], self.minPos[1], self.maxPos[0], self.maxPos[1]), False),
                loop
            )
        except Exception as e:
            self.logger.error(f"WebSocket: Failed to send lanes position: {e}")
            remove_session(self)

    def trigger_lights_update(self, loop):
        """Trigger an update for the lights in this session."""
        if not self.focused:
            self.logger.debug("WebSocket: Session not focused, skipping lights update.")
            return
        try:
            lights = []
            if self.minPos[0] is not None and self.maxPos[0] is not None:
                lights = getTrafficLightIn(self.minPos[0], self.minPos[1], self.maxPos[0], self.maxPos[1])
            else:
                lights = getTrafficLight()
            asyncio.run_coroutine_threadsafe(
                self.send("traffic_light/state", lights, False),
                loop
            )
        except Exception as e:
            self.logger.error(f"WebSocket: Failed to send vehicles update: {e}")
            remove_session(self)


    def shape_bb_frame(self, shape):
        """Check if the shape is within the bounding box frame."""
        if not shape or len(shape) < 2:
            return False

        minX, minY = self.minPos
        maxX, maxY = self.maxPos
        if maxX < minX:
            minX, maxX = maxX, minX
        if maxY < minY:
            minY, maxY = maxY, minY

        return any(minX <= pt[0] <= maxX and minY <= pt[1] <= maxY for pt in shape)