from master.database import connect_to_database
import json

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
                "shape": json.loads(lane[0]).get('coordinates', []),
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