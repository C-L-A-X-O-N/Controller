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
        zone = data.get("zone", 0)
        self.logger.info(f"Handling vehicle position for zone {zone}")
        
        # Track vehicles in the current data
        vehiclesPresent = set()
        
        # Prepare batch operations
        vehicles_to_upsert = []
        
        # Process all vehicles first without database operations
        for vehicle in data.get("data", []):
            vehicle_id = vehicle['id']
            vehiclesPresent.add(vehicle_id)
            
            # Extract position and other properties
            lat, lon = vehicle['position'][1], vehicle['position'][0]
            v_type = vehicle.get('type')
            angle = vehicle.get('angle')
            speed = vehicle.get('speed')
            accident = vehicle.get('accident', False)
            
            # Check if vehicle exists and if data has changed
            if (vehicle_id not in vehicles or 
                vehicles[vehicle_id]['position'] != [lat, lon] or
                vehicles[vehicle_id]['type'] != v_type or
                vehicles[vehicle_id]['angle'] != angle or
                vehicles[vehicle_id]['speed'] != speed or
                vehicles[vehicle_id]['accident'] != accident):
                
                # Queue for upsert
                vehicles_to_upsert.append((
                    vehicle_id, lat, lon, v_type, angle, speed, accident, zone
                ))
                
                # Update cache
                vehicles[vehicle_id] = {
                    "id": vehicle_id,
                    "position": [lat, lon],
                    "type": v_type,
                    "angle": angle,
                    "speed": speed,
                    "accident": accident,
                    "zone": zone
                }
        
        # Execute database operations in batches
        with self.database.cursor() as cursor:
            # Batch upsert
            if vehicles_to_upsert:
                args_str = ','.join(
                    cursor.mogrify("(%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s)", x).decode('utf-8')
                    for x in vehicles_to_upsert
                )
                cursor.execute(
                    f"""
                    INSERT INTO vehicles (id, geom, type, angle, speed, accident, zone)
                    VALUES {args_str}
                    ON CONFLICT (id) DO UPDATE SET
                        geom = EXCLUDED.geom,
                        type = EXCLUDED.type,
                        angle = EXCLUDED.angle,
                        speed = EXCLUDED.speed,
                        accident = EXCLUDED.accident,
                        zone = EXCLUDED.zone
                    """
                )
            
            # Remove vehicles that are no longer present
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

        self.logger.debug(f"Vehicle positions updated: {len(vehicles_to_upsert)} upserted, {len(vehicles_to_remove) if 'vehicles_to_remove' in locals() else 0} removed")

    def handle_lane_position(self, loop, data):
        self.logger.info(f"Handling lane position data")
        lanes = self.laneCache.getCached()
        
        # Define WKT conversion function
        def to_wkt_multilinestring(shape):
            if not isinstance(shape, list) or len(shape) < 2:
                return None
            try:
                points = ", ".join(f"{float(pt[1])} {float(pt[0])}" for pt in shape)
                return f"MULTILINESTRING(({points}))"
            except (TypeError, ValueError, IndexError):
                return None
        
        # Prepare batch operations
        lanes_to_insert = []
        lanes_to_update = []
        
        # Process all lanes first without database operations
        for lane in data["data"]:
            lane['jam'] = 0
            lane_id = lane['id']
            
            # Only convert shape to WKT if needed
            if lane_id not in lanes or lanes[lane_id].get('shape') != lane['shape']:
                wkt_shape = to_wkt_multilinestring(lane['shape'])
                if wkt_shape == "MULTILINESTRING(())":
                    continue
                    
                if lane_id not in lanes:
                    # Queue for insertion
                    lanes_to_insert.append((
                        lane_id,
                        wkt_shape,
                        lane.get('priority', 0),
                        lane.get('type'),
                        data.get("zone", 0)
                    ))
                    lanes[lane_id] = lane
                else:
                    # Queue for update
                    lanes_to_update.append((
                        wkt_shape,
                        lane.get('priority', 0),
                        lane.get('type'),
                        lane_id
                    ))
                    lanes[lane_id] = lane
        
        # Execute database operations in batches
        with self.database.cursor() as cursor:
            # Batch insert
            if lanes_to_insert:
                args_str = ','.join(cursor.mogrify("(%s, ST_SetSRID(ST_GeomFromText(%s), 4326), %s, %s, %s, 0)", x).decode('utf-8') 
                                   for x in lanes_to_insert)
                cursor.execute(
                    f"""
                    INSERT INTO lanes (id, geom, priority, type, zone, jam)
                    VALUES {args_str}
                    """
                )
            
            # Batch update using executemany
            if lanes_to_update:
                cursor.executemany(
                    """
                    UPDATE lanes SET geom = ST_SetSRID(ST_GeomFromText(%s), 4326), 
                    priority = %s, type = %s WHERE id = %s
                    """,
                    lanes_to_update
                )
                
            self.database.commit()
        
        logging.info(f"Updated {len(lanes_to_insert) + len(lanes_to_update)} lanes in the database. ({len(lanes)} total lanes cached)")
        self.laneCache.setCached(lanes)
        self.logger.info("Lane positions updated in the database.")
        
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