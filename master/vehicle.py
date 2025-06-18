from master.database import connect_to_database
import json

def getVehicles():
    vehiclesFormatted = []
    db = connect_to_database()
    with db.cursor() as cursor:
        cursor.execute("SELECT ST_AsGeoJSON(geom) AS geometry, id, type, angle, speed, accident FROM vehicles;")
        vehicles = cursor.fetchall()
        for vehicle in vehicles:
            vehiclesFormatted.append({
                "id": vehicle[1],
                "position": json.loads(vehicle[0]).get('coordinates', []),
                "type": vehicle[2],
                "angle": vehicle[3],
                "speed": vehicle[4],
                "accident": vehicle[5]
            })
    return vehiclesFormatted

def getVehiclesIn(minX, minY, maxX, maxY):
    # minX, minY: north-west (lon, lat), maxX, maxY: south-east (lon, lat)
    # ST_MakeEnvelope expects (xmin, ymin, xmax, ymax)
    # xmin = min(minX, maxX), xmax = max(minX, maxX)
    # ymin = min(minY, maxY), ymax = max(minY, maxY)
    # Attention: lat = Y, lon = X
    xmin = min(minX, maxX)
    xmax = max(minX, maxX)
    ymin = min(minY, maxY)
    ymax = max(minY, maxY)
    vehiclesFormatted = []
    db = connect_to_database()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT ST_AsGeoJSON(geom) AS geometry, id, type, angle, speed, accident
            FROM vehicles
            WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326);
        """, (xmin, ymin, xmax, ymax))
        vehicles = cursor.fetchall()
        for vehicle in vehicles:
            vehiclesFormatted.append({
                "id": vehicle[1],
                "position": json.loads(vehicle[0]).get('coordinates', []),
                "type": vehicle[2],
                "angle": vehicle[3],
                "speed": vehicle[4],
                "accident": vehicle[5]
            })
    return vehiclesFormatted

def getVehiclesIndexed():
    lanes = getVehicles()
    lanesIndexed = {}
    for lane in lanes:
        lanesIndexed[lane['id']] = lane
    return lanesIndexed