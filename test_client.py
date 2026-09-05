import asyncio
import websockets
import json

async def main():
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        move = {"from": [-6, 4], "to": [-4, 2], "player": 0}
        await ws.send(json.dumps(move))
        response = await ws.recv()
        print(response)

asyncio.run(main())