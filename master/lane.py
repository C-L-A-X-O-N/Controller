from master.database import connect_to_database
import json

class LaneCache:
    lanes = {}

    def __init__(self):
        self.lanes = getLanesIndexed()

    def getCached(self):
        return self.lanes
    
    def setCached(self, lanes):
        self.lanes = lanes
    



def getLanes():
    """Returns the lanes for the current session."""
    lanesFormatted = []
    db = connect_to_database()
    with db.cursor() as cursor:
        cursor.execute("SELECT ST_AsGeoJSON(geom) AS geometry, id, priority, type, jam FROM lanes;")
        lanes = cursor.fetchall()
        for lane in lanes:
            lanesFormatted.append({
                "id": lane[1],
                "shape": json.loads(lane[0]).get('coordinates', [])[0],
                "priority": lane[2],
                "type": lane[3],
                "jam": lane[4]
            })
    return lanesFormatted

def getLanesIndexed():
    """Returns the lanes indexed by their ID."""
    lanes = getLanes()
    lanesIndexed = {}
    for lane in lanes:
        lanesIndexed[lane['id']] = lane
    return lanesIndexed

def getLanesIn(minX, minY, maxX, maxY):
    """Returns the lanes in the given bounding box."""
    lanesFormatted = []
    db = connect_to_database()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT ST_AsGeoJSON(geom) AS geometry, id, priority, type, jam
            FROM lanes
            WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326);
        """, (minX, minY, maxX, maxY))
        lanes = cursor.fetchall()
        for lane in lanes:
            lanesFormatted.append({
                "id": lane[1],
                "shape": json.loads(lane[0]).get('coordinates', [])[0],
                "priority": lane[2],
                "type": lane[3],
                "jam": lane[4]
            })
    return lanesFormatted