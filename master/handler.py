from .database import connect_to_database
from .mqtt_client import publish_to_websocket
from .lane import getLanesIndexed, LaneCache
from .vehicle import VehicleCache
from .traffic_light import getTrafficLightIndexed
import logging, json
from .session.registry import trigger_vehicles_update, trigger_lanes_update, trigger_lanes_position

class Handler:
    database = None
    logger = None
    laneCache = None
    vehicleCache = None

    def __init__(self):   
        self.database = connect_to_database()
        self.laneCache = LaneCache()
        self.vehicleCache = VehicleCache()
        self.logger = logging.getLogger(__name__)

    def handle_vehicle_position(self, loop, data):
        vehicles = self.vehicleCache.getCached()
        with self.database.cursor() as cursor:
            vehiclesPresent = set()
            zone = data.get("zone", 0)
            self.logger.info(f"Handling vehicle position for zone {zone}")
            for vehicle in data.get("data", []):
                vehiclesPresent.add(vehicle['id'])
                if vehicle['id'] not in vehicles:
                    cursor.execute(
                        """
                        INSERT INTO vehicles (id, geom, type, angle, speed, accident, zone)
                        VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            geom = EXCLUDED.geom,
                            type = EXCLUDED.type,
                            angle = EXCLUDED.angle,
                            speed = EXCLUDED.speed,
                            accident = EXCLUDED.accident,
                            zone = EXCLUDED.zone
                        """,
                        (
                            vehicle['id'],
                            vehicle['position'][1],  # latitude
                            vehicle['position'][0],  # longitude
                            vehicle.get('type'),
                            vehicle.get('angle'),
                            vehicle.get('speed'),
                            vehicle.get('accident', False),
                            data.get("zone", 0)
                        )
                    )
                    vehicles[vehicle['id']] = {
                        "id": vehicle['id'],
                        "position": [vehicle['position'][1], vehicle['position'][0]],
                        "type": vehicle.get('type'),
                        "angle": vehicle.get('angle'),
                        "speed": vehicle.get('speed'),
                        "accident": vehicle.get('accident', False),
                        "zone": data.get("zone", 0)
                    }
                else:
                    # Check if the vehicle position has changed
                    old_vehicle = vehicles[vehicle['id']]
                    if (old_vehicle['position'] == [vehicle['position'][1], vehicle['position'][0]] and
                        old_vehicle['type'] == vehicle.get('type') and
                        old_vehicle['angle'] == vehicle.get('angle') and
                        old_vehicle['speed'] == vehicle.get('speed') and
                        old_vehicle['accident'] == vehicle.get('accident', False)):
                        # self.logger.debug(f"No change in vehicle {vehicle['id']}, skipping update.")
                        continue
                    
                    cursor.execute(
                        """
                        UPDATE vehicles SET geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326), type = %s, angle = %s, speed = %s, accident = %s, zone = %s WHERE id = %s
                        """,
                        (
                            vehicle['position'][1],  # latitude
                            vehicle['position'][0],  # longitude
                            vehicle.get('type'),
                            vehicle.get('angle'),
                            vehicle.get('speed'),
                            vehicle.get('accident', False),
                            data.get("zone", 0),
                            vehicle['id']
                        )
                    )
                    vehicles[vehicle['id']] = {
                        "id": vehicle['id'],
                        "position": [vehicle['position'][1], vehicle['position'][0]],
                        "type": vehicle.get('type'),
                        "angle": vehicle.get('angle'),
                        "speed": vehicle.get('speed'),
                        "accident": vehicle.get('accident', False),
                        "zone": data.get("zone", 0)
                    }

            # Remove vehicles that are no longer present
            # Remove vehicles that are no longer present using a single SQL query
            vehicles_to_remove = [vid for vid in vehicles.keys() if vid not in vehiclesPresent]
            if vehicles_to_remove:
                format_strings = ','.join(['%s'] * len(vehicles_to_remove))
                cursor.execute(
                    f"DELETE FROM vehicles WHERE id IN ({format_strings}) AND zone = %s",
                    vehicles_to_remove + [zone]
                )
                for vehicle_id in vehicles_to_remove:
                    del vehicles[vehicle_id]
            self.database.commit()
            self.vehicleCache.setCached(vehicles)

        self.logger.debug("Vehicle positions updated in the database.")

    def handle_lane_position(self, loop, data):
        self.logger.info(f"Handling lane position data")
        # save/replace in the database
        def to_wkt_multilinestring(shape):
            if not isinstance(shape, list) or len(shape) < 2:
                return None  # Trop court pour faire une ligne

            try:
                points = ", ".join(f"{float(pt[1])} {float(pt[0])}" for pt in shape)
                return f"MULTILINESTRING(({points}))"
            except (TypeError, ValueError, IndexError):
                return None

        lanes = self.laneCache.getCached()
        with self.database.cursor() as cursor:
            for lane in data["data"]:
                lane['jam'] = 0
                wkt_shape = to_wkt_multilinestring(lane['shape'])
                if wkt_shape == "MULTILINESTRING(())":
                    continue 


                if lane['id'] not in lanes:
                    cursor.execute(
                        """
                        INSERT INTO lanes (id, geom, priority, type, zone, jam)
                        VALUES (%s, ST_SetSRID(ST_GeomFromText(%s), 4326), %s, %s, %s, 0)
                        """,
                        # ON CONFLICT (id) DO UPDATE SET
                        #     geom = EXCLUDED.geom,
                        #     priority = EXCLUDED.priority,
                        #     type = EXCLUDED.type
                        # """,
                        (
                            lane['id'],
                            wkt_shape,
                            lane.get('priority', 0),
                            lane.get('type'),
                            data.get("zone", 0)
                        )
                    )
                    lanes[lane['id']] = lane
                else:
                    # check if the lane shape has changed
                    if "shape" in lanes[lane['id']] and lanes[lane['id']]['shape'] == lane['shape']:
                        # self.logger.debug(f"No change in lane {lane['id']}, skipping update.")
                        continue
                    cursor.execute(
                        """
                        UPDATE lanes SET geom = ST_SetSRID(ST_GeomFromText(%s), 4326), priority = %s, type = %s WHERE id = %s
                        """,
                        (
                            wkt_shape,
                            lane.get('priority', 0),
                            lane.get('type'),
                            lane['id']
                        )
                    )
                    lanes[lane['id']] = lane

            self.database.commit()
            logging.info(f"Updated {len(data['data'])} lanes in the database. ({len(lanes)} total lanes cached)")
            self.laneCache.setCached(lanes)

        self.logger.debug("Lane positions updated in the database.")

        trigger_lanes_position(loop)

    def handle_lane_state(self, loop, data):
        self.logger.debug(f"Handling lane state data")
        lanes = self.laneCache.getCached()
        # save/replace in the database
        newData = []
        with self.database.cursor() as cursor:
            for lane in data["data"]:
                if lane['id'] not in lanes:
                    continue
                # Check if lane state has changed
                if lane['traffic_jam'] == lanes[lane['id']]['jam']:
                    # self.logger.debug(f"No change in traffic jam state for lane {lane['id']}, skipping update.")
                    continue
                jam = lane.get('traffic_jam', 0)
                if jam == None:
                    jam = 0
                cursor.execute(
                    """
                    UPDATE lanes SET jam = %s WHERE id = %s
                    """,
                    (jam, lane['id'])
                )
                old = lanes[lane['id']]
                if "shape" not in lane and "shape" in old:
                    lane['shape'] = old['shape']
                lane['jam'] = jam
                lanes[lane['id']] = lane
                newData.append(lane)
            self.database.commit()
            self.laneCache.setCached(lanes)

        self.logger.debug("Lane states updated in the database.")
        # trigger_lanes_update(loop, newData)

    def handle_lights_position(self, loop, data):
        self.logger.debug(f"Handling traffic light position data")
        # save/replace in the database
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM traffic_lights WHERE zone = %s;
                """, [
                    data.get("zone", 0)
                ]
            )
            for light in data["data"]:
                cursor.execute(
                    """
                    INSERT INTO traffic_lights (id, geom, in_lane, out_lane, via_lane, zone)
                    VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        geom = EXCLUDED.geom,
                        in_lane = EXCLUDED.in_lane,
                        out_lane = EXCLUDED.out_lane,
                        via_lane = EXCLUDED.via_lane,
                        zone = EXCLUDED.zone
                    """,
                    (
                        light['id'],
                        light.get('position')[1],
                        light.get('position')[0],
                        light.get('in_lane'),
                        light.get('out_lane'),
                        light.get('via_lane'),
                        data.get("zone", 0)
                    )
                )

            self.database.commit()

        self.logger.debug("Traffic light positions updated in the database.")
        publish_to_websocket(
            loop,
            "traffic_light/position",
            data.get("data", [])
        )

    def handle_lights_state(self, loop, data):
        self.logger.debug(f"Handling traffic light state data")
        # save/replace in the database
        lights = getTrafficLightIndexed()
        with self.database.cursor() as cursor:
            for light in data["data"]:
                if light['id'] not in lights:
                    # self.logger.warning(f"Traffic light {light['id']} not found in database, skipping update.")
                    continue
                cursor.execute(
                    """
                    UPDATE traffic_lights SET state = %s WHERE id = %s
                    """,
                    (light['state'], light['id'])
                )
            self.database.commit()

        self.logger.debug("Traffic light states updated in the database.")

handler = None

def setup_handler():
    global handler
    if handler is None:
        handler = Handler()
    return handler