from master.websocket_server import broadcast_websocket_message
import asyncio

traffic_lights = []

def setLanes(_lanes):
    """Sets the lanes for the current session."""
    global traffic_lights
    lanes = _lanes
    asyncio.run(broadcast_websocket_message("lanes/position", lanes))

def getLanes():
    """Returns the lanes for the current session."""
    global traffic_lights
    return lanes