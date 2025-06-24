import json, websockets, logging, asyncio
from master.lane import getLanes, getLanesIn
from master.traffic_light import getTrafficLight, getTrafficLightIn
from master.session.registry import remove_session
from master.vehicle import getVehiclesIn, getVehicles

class Session:
    def __init__(self, websocket):
        self.websocket = websocket
        self.logger = logging.getLogger(__name__ + ":" + str(id(self)))
        self.minPos = [None, None]
        self.maxPos = [None, None]
        self.focused = False

    async def init(self):
        await self.websocket.send(json.dumps({
            "type": "traffic_light/position",
            "data": getTrafficLight()
        }))
        self.logger.debug("WebSocket: Initial lanes sent to client.")
        self.logger.info("WebSocket: Client Connected.")

    async def tick(self):
        try:
            message = await asyncio.wait_for(self.websocket.recv(), timeout=60.0)  # Timeout après 60 secondes
            try:
                data = json.loads(message)
                if "type" not in data or "data" not in data:
                    self.logger.error("WebSocket: Invalid message format received.")
                    return
            except json.JSONDecodeError:
                self.logger.error(f"WebSocket: Invalid JSON received: {message}")
                return
        except asyncio.TimeoutError:
            self.logger.debug("WebSocket: Timeout waiting for message, sending ping.")
            try:
                # Envoyer un ping pour vérifier si la connexion est toujours active
                pong_waiter = await self.websocket.ping()
                await asyncio.wait_for(pong_waiter, timeout=10.0)
                return  # La connexion est toujours bonne, continuer
            except Exception:
                # Si le ping échoue, lever une exception pour fermer la connexion
                self.logger.warning("WebSocket: Ping failed, closing connection.")
                raise websockets.exceptions.ConnectionClosedError(1000, "Ping timeout")
        
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
        elif data["type"] == "command/traffic_light/next_phase":
            light_id = data["data"].get("id")
            if not light_id:
                
                return
            
            from master.mqtt_client import mqtt_publish_traffic_light_next_phase
            mqtt_publish_traffic_light_next_phase({"id": light_id})
        elif data["type"] == "session/update_accidents":
            loop = asyncio.get_event_loop()
            self.trigger_accidents_update(loop)
        elif data["type"] == "traffic_light/set_state":
            light_id = data["data"].get("id")
            new_state = data["data"].get("state")

            if not light_id or not new_state:
                self.logger.warning("Missing 'id' or 'state'")
                return

            from master.handler import handler
            handler.send_traffic_light_state_command(light_id, new_state)

    async def send(self, message_type, data, dump_json=False):
        try:
            if dump_json:
                try:
                    data = json.loads(data)
                except json.JSONDecodeError as e:
                    self.logger.error(f"WebSocket: Failed to parse JSON for dump_json=True: {e}")
                    return False
                    
            message = {
                "type": message_type,
                "data": data
            }
            
            try:
                json_message = json.dumps(message)
            except (TypeError, ValueError) as e:
                self.logger.error(f"WebSocket: Failed to serialize message to JSON: {e}")
                return False
                
            try:
                await asyncio.wait_for(
                    self.websocket.send(json_message), 
                    timeout=5.0  # Timeout pour l'envoi
                )
                return True
            except asyncio.TimeoutError:
                self.logger.warning("WebSocket: Timeout when sending message.")
                raise websockets.exceptions.ConnectionClosedError(1001, "Send timeout")
                
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("WebSocket: Connection closed while trying to send message.")
            remove_session(self)
            return False
        except Exception as e:
            self.logger.error(f"WebSocket: Error sending message: {e}")
            return False

    def set_frame(self, minX, minY, maxX, maxY):
        self.minPos = [minX, minY]
        self.maxPos = [maxX, maxY]
        self.logger.debug(f"WebSocket: Frame set to {self.minPos} - {self.maxPos}")

    def trigger_vehicle_update(self, loop):
        """Trigger an update for the vehicles in this session."""
        if not self.focused:
            self.logger.info("WebSocket: Session not focused, skipping vehicle update.")
            return
        self.logger.info("WebSocket: Triggering vehicle update.")
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
        
    def trigger_lane_update(self, loop):
        """Trigger an update for the lanes in this session."""
        if not self.focused:
            # self.logger.warning("WebSocket: Session not focused, skipping lane update.")
            return
        try:
            dataToSend = []
            for lane in getLanesIn(self.minPos[0], self.minPos[1], self.maxPos[0], self.maxPos[1]):
                dataToSend.append({
                    "id": lane["id"],
                    "state": lane["jam"]
                })
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

    def trigger_accidents_update(self, loop):
        """Trigger an update for accidents in this session."""
        if not self.focused:
            self.logger.debug("WebSocket: Session not focused, skipping accidents update.")
            return
        try:
            # Récupérer les accidents de la base de données
            from master.database import connect_to_database
            db = connect_to_database()
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT vehicle_id as id,
                           ST_X(geom) as longitude,
                           ST_Y(geom) as latitude,
                           type,
                           start_time, zone, duration
                    FROM accidents
                    """,
                )

                accidents = []
                for row in cursor.fetchall():
                    # Déterminer si nous avons une colonne duration dans les résultats
                    if len(row) >= 7:  # Avec duration
                        accident_data = {
                            "id": row[0],
                            "position": [row[2], row[1]],  # [latitude, longitude]
                            "type": row[3],
                            "start_time": row[4],
                            "zone": row[5],
                            "duration": row[6]
                        }
                    else:  # Sans duration
                        accident_data = {
                            "id": row[0],
                            "position": [row[2], row[1]],  # [latitude, longitude]
                            "type": row[3],
                            "start_time": row[4],
                            "zone": row[5],
                            "duration": 10  # Valeur par défaut
                        }
                    accidents.append(accident_data)

            asyncio.run_coroutine_threadsafe(
                self.send("accident/position", accidents, False),
                loop
            )
        except Exception as e:
            self.logger.error(f"WebSocket: Failed to send accidents update: {e}")
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