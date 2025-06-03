from master.websocket_server import broadcast_websocket_message
import asyncio

lanes = []

def setLanes(_lanes):
    """Sets the lanes for the current session."""
    global lanes
    lanes = _lanes
    asyncio.run(broadcast_websocket_message("lanes/position", lanes))

def getLanes():
    """Returns the lanes for the current session."""
    global lanes
    return lanes