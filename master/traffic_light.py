from master.websocket_server import broadcast_websocket_message
import asyncio

traffic_lights = []

def setTrafficLight(_lights):
    global traffic_lights
    traffic_lights = _lights
    asyncio.run(broadcast_websocket_message("traffic_light/position", traffic_lights))

def getTrafficLight():
    global traffic_lights
    return traffic_lights