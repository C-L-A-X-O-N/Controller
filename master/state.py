import asyncio

from master.websocket_server import broadcast_websocket_message

STATE = {
    "IN_PROGRESS",
    "SETTING_UP",
    "BREAK"
}

current_state = None

def setState(_state, loop=None):
    """Sets the lanes for the current session."""
    global lanes

    if _state not in STATE:
        raise ValueError(f"Invalid state: {_state}. Must be one of {STATE}")

    lanes = _state

    if loop is None:
        loop = asyncio.get_event_loop()

    # Envoi des données au webSocket
    asyncio.run_coroutine_threadsafe(
        broadcast_websocket_message("state", _state),
        loop
    )

def getState():
    """Returns the state for the current session."""
    global current_state
    return current_state