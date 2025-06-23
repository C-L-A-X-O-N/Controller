from master.database import connect_to_database

def getTrafficLight():
    lightsFormatted = []
    db = connect_to_database()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT id, in_lane, out_lane, via_lane, ST_Y(geom) AS lat, ST_X(geom) AS lon
            FROM traffic_lights;
        """)
        traffic_lights = cursor.fetchall()
        for tl in traffic_lights:
            lightsFormatted.append({
                "id": tl[0],
                "in_lane": tl[1],
                "out_lane": tl[2],
                "via_lane": tl[3],
                "stop_lat": tl[4],
                "stop_lon": tl[5]
            })
    return lightsFormatted

def getTrafficLightIn(minX, minY, maxX, maxY):
    # minX, minY: north-west (lon, lat), maxX, maxY: south-east (lon, lat)
    # ST_MakeEnvelope expects (xmin, ymin, xmax, ymax)
    # xmin = min(minX, maxX), xmax = max(minX, maxX)
    # ymin = min(minY, maxY), ymax = max(minY, maxY)
    # Attention: lat = Y, lon = X
    xmin = min(minX, maxX)
    xmax = max(minX, maxX)
    ymin = min(minY, maxY)
    ymax = max(minY, maxY)
    lightsFormatted = []
    db = connect_to_database()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT id, in_lane, out_lane, via_lane,
                   ST_Y(geom) AS lat, ST_X(geom) AS lon, state
            FROM traffic_lights
            WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326);
        """, (xmin, ymin, xmax, ymax))
        traffic_lights = cursor.fetchall()
        for tl in traffic_lights:
            lightsFormatted.append({
                "id": tl[0],
                "in_lane": tl[1],
                "out_lane": tl[2],
                "via_lane": tl[3],
                "stop_lat": tl[4],
                "stop_lon": tl[5],
                "state": tl[6] if len(tl) > 6 else None
            })
    return lightsFormatted

def getTrafficLightIndexed():
    lights = getTrafficLight()
    lightsIndexed = {}
    for light in lights:
        lightsIndexed[light['id']] = light
    return lightsIndexed