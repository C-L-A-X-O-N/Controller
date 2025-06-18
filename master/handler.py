from .database import connect_to_database
from .mqtt_client import publish_to_websocket
from .lane import getLanes, getLanesIndexed
from .vehicle import getVehicles
from .traffic_light import getTrafficLight, getTrafficLightIndexed
import logging, json
from .session.registry import trigger_vehicles_update, trigger_lanes_update

class Handler:
    database = None
    logger = None

    def __init__(self):   
        self.database = connect_to_database()
        self.logger = logging.getLogger(__name__)

    def handle_vehicle_position(self, loop, data):
        self.logger.debug(f"Handling vehicle position")
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE TABLE vehicles;
                """
            )
            for vehicle in data:
                cursor.execute(
                    """
                    INSERT INTO vehicles (id, geom, type, angle, speed, accident)
                    VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        geom = EXCLUDED.geom,
                        type = EXCLUDED.type,
                        angle = EXCLUDED.angle,
                        speed = EXCLUDED.speed,
                        accident = EXCLUDED.accident
                    """,
                    (
                        vehicle['id'],
                        vehicle['position'][1],  # latitude
                        vehicle['position'][0],  # longitude
                        vehicle.get('type'),
                        vehicle.get('angle'),
                        vehicle.get('speed'),
                        vehicle.get('accident', False)
                    )
                )

            self.database.commit()

        self.logger.debug("Vehicle positions updated in the database.")

        trigger_vehicles_update(loop)

    def handle_lane_position(self, loop, data):
        self.logger.debug(f"Handling lane position data")
        # save/replace in the database
        def to_wkt_multilinestring(shape):
            if not isinstance(shape, list) or len(shape) < 2:
                return None  # Trop court pour faire une ligne

            try:
                points = ", ".join(f"{float(pt[1])} {float(pt[0])}" for pt in shape)
                return f"MULTILINESTRING(({points}))"
            except (TypeError, ValueError, IndexError):
                return None

        lanes = getLanesIndexed()
        with self.database.cursor() as cursor:
            for lane in data:
                wkt_shape = to_wkt_multilinestring(lane['shape'])
                if wkt_shape == "MULTILINESTRING(())":
                    continue 


                if lane['id'] not in lanes:
                    cursor.execute(
                        """
                        INSERT INTO lanes (id, geom, priority, type)
                        VALUES (%s, ST_SetSRID(ST_GeomFromText(%s), 4326), %s, %s)
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
                            lane.get('type')
                        )
                    )
                else:
                    # check if the lane shape has changed
                    if lanes[lane['id']]['shape'] == lane['shape']:
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

            self.database.commit()

        self.logger.debug("Lane positions updated in the database.")

        publish_to_websocket(
            loop,
            "lanes/position",
            getLanes()
        )

    def handle_lane_state(self, loop, data):
        self.logger.debug(f"Handling lane state data")
        lanes = getLanesIndexed()
        # save/replace in the database
        newData = []
        with self.database.cursor() as cursor:
            for lane in data:
                if lane['id'] not in lanes:
                    self.logger.warning(f"Lane {lane['id']} not found in database, skipping update.")
                    continue
                # Check if lane state has changed
                if lane['traffic_jam'] == lanes[lane['id']]['jam']:
                    # self.logger.debug(f"No change in traffic jam state for lane {lane['id']}, skipping update.")
                    continue
                cursor.execute(
                    """
                    UPDATE lanes SET jam = %s WHERE id = %s
                    """,
                    (lane['traffic_jam'], lane['id'])
                )
                old = lanes[lane['id']]
                lane['shape'] = old['shape']
                newData.append(lane)
            self.database.commit()

        self.logger.debug("Lane states updated in the database.")
        trigger_lanes_update(loop, newData)

    def handle_lights_position(self, loop, data):
        self.logger.debug(f"Handling traffic light position data")
        # save/replace in the database
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE TABLE traffic_lights;
                """
            )
            for light in data:
                cursor.execute(
                    """
                    INSERT INTO traffic_lights (id, geom, in_lane, out_lane, via_lane)
                    VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        geom = EXCLUDED.geom,
                        in_lane = EXCLUDED.in_lane,
                        out_lane = EXCLUDED.out_lane,
                        via_lane = EXCLUDED.via_lane
                    """,
                    (
                        light['id'],
                        light.get('stop_lon'),
                        light.get('stop_lat'),
                        light.get('in_lane'),
                        light.get('out_lane'),
                        light.get('via_lane')
                    )
                )

            self.database.commit()

        self.logger.debug("Traffic light positions updated in the database.")
        publish_to_websocket(
            loop,
            "traffic_light/position",
            data
        )

    def handle_lights_state(self, loop, data):
        self.logger.debug(f"Handling traffic light state data")
        # save/replace in the database
        lights = getTrafficLightIndexed()
        with self.database.cursor() as cursor:
            for light in data:
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
        publish_to_websocket(
            loop,
            "traffic_light/state",
            data
        )

handler = None

def setup_handler():
    global handler
    if handler is None:
        handler = Handler()
    return handler