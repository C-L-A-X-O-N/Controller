from master.websocket_server import broadcast_websocket_message
import asyncio

lanes = []

def setLanes(_lanes, loop=None):
    """Sets the lanes for the current session."""
    global lanes
    lanes = _lanes
    if loop is None:
        loop = asyncio.get_event_loop()
    asyncio.run_coroutine_threadsafe(
        broadcast_websocket_message("lanes/position", lanes),
        loop
    )

def getLanes():
    """Returns the lanes for the current session."""
    global lanes
    return lanes