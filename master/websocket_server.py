import json
import logging
import asyncio
import websockets

from .session.session import Session
from .session.registry import add_session, remove_session, get_sessions

logger = logging.getLogger(__name__)

async def broadcast_websocket_message(message_type, data, dump_json = False):
    for session in get_sessions():
        await session.send(message_type, data, dump_json)

async def handle_websocket_connection(websocket):
    logger.info("WebSocket: Client Connected.")
    session = None
    try:
        session = Session(websocket)
        await session.init()
        add_session(session)
        while True:
            await session.tick()
    finally:
        if session != None:
            logger.info("WebSocket: Client Disconnected.")
            remove_session(session)


async def start_websocket_server():
    """Démarrage du serveur WebSocket."""
    async with websockets.serve(handle_websocket_connection, "0.0.0.0", 7900):
        await asyncio.Future()  # run forever