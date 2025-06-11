import json
import logging
import asyncio
import websockets

logger = logging.getLogger(__name__)
connected_websockets = set()

async def broadcast_websocket_message(message_type, data, dump_json = False):
    disconnected = set()
    if dump_json:
        data = json.loads(data)
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
    from master.lane import getLanes
    from master.traffic_light import getTrafficLight

    """Gestion des connexions WebSocket."""
    logger.info("WebSocket: Client Connected.")
    try:
        connected_websockets.add(websocket)
        await websocket.send(json.dumps({
            "type": "lanes/position",
            "data": getLanes()
        }))
        await websocket.send(json.dumps({
            "type": "traffic_light/position",
            "data": getTrafficLight()
        }))
        logger.debug("WebSocket: Initial lanes sent to client.")
        while True:
            message = await websocket.recv()

            data = json.loads(message)
            print(data)

            logger.debug(f"WebSocket: Received message: {message}")
    except websockets.ConnectionClosedError:
        logger.error("WebSocket: Client Disconnected.")
    finally:
        connected_websockets.remove(websocket)


async def start_websocket_server():
    """Démarrage du serveur WebSocket."""
    async with websockets.serve(handle_websocket_connection, "0.0.0.0", 7890):
        await asyncio.Future()  # run forever