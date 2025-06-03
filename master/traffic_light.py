from master.websocket_server import broadcast_websocket_message
import asyncio

traffic_lights = []

def setTrafficLight(_lights, loop = None):
    global traffic_lights
    traffic_lights = _lights
    if loop is None:
        loop = asyncio.get_event_loop()
    asyncio.run_coroutine_threadsafe(
        broadcast_websocket_message("traffic_light/position", traffic_lights),
        loop
    )

def getTrafficLight():
    global traffic_lights
    return traffic_lights