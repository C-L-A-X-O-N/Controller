import json
import logging
import asyncio
import websockets

logger = logging.getLogger(__name__)
connected_websockets = set()

async def broadcast_websocket_message(message_type, data):
    disconnected = set()
    for ws in connected_websockets:
        try:
            await ws.send(json.dumps({
                "type": message_type,
                "data": data
            }))
        except websockets.ConnectionClosed:
            disconnected.add(ws)
    connected_websockets.difference_update(disconnected)

async def handle_websocket_connection(websocket):
    """Gestion des connexions WebSocket."""
    logger.info("WebSocket: Client Connected.")
    try:
        connected_websockets.add(websocket)
        while True:
            name = await websocket.recv()
            age = await websocket.recv()

            if not name or not age:
                logger.error("Error Receiving Value from Client.")
                break

            logger.info(f"Details Received - Name: {name}, Age: {age}")
            if int(age) < 18:
                await websocket.send(f"Sorry! {name}, You can't join the club.")
            else:
                await websocket.send(f"Welcome aboard, {name}.")
    except websockets.ConnectionClosedError:
        logger.error("WebSocket: Client Disconnected.")
    finally:
        connected_websockets.remove(websocket)


async def start_websocket_server():
    """Démarrage du serveur WebSocket."""
    async with websockets.serve(handle_websocket_connection, "localhost", 7890):
        await asyncio.Future()  # run forever