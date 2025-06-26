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
            try:
                await session.tick()
            except websockets.exceptions.ConnectionClosedError as e:
                logger.warning(f"WebSocket: Connection closed with error: {e}")
                break
            except websockets.exceptions.ConnectionClosedOK:
                logger.info("WebSocket: Connection closed normally.")
                break
            except asyncio.CancelledError:
                logger.info("WebSocket: Connection cancelled.")
                break
            except Exception as e:
                logger.error(f"WebSocket: Error in session tick: {e}")
                break
    except websockets.exceptions.ConnectionClosedError as e:
        logger.warning(f"WebSocket: Connection closed with error during setup: {e}")
    except Exception as e:
        logger.error(f"WebSocket: Error in connection handler: {e}")
    finally:
        if session is not None:
            logger.info("WebSocket: Client Disconnected.")
            try:
                remove_session(session)
            except Exception as e:
                logger.error(f"WebSocket: Error removing session: {e}")


async def start_websocket_server():
    """Démarrage du serveur WebSocket."""
    async with websockets.serve(handle_websocket_connection, "0.0.0.0", 7900):
        await asyncio.Future()  # run forever