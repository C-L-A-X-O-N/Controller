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

def getTrafficLightIndexed():
    lights = getTrafficLight()
    lightsIndexed = {}
    for light in lights:
        lightsIndexed[light['id']] = light
    return lightsIndexed