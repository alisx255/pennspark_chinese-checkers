"""
Starting point for wiring your existing Chinese checkers logic into a
WebSocket multiplayer server.

Run with: uvicorn main:app --reload
Requires: pip install fastapi "uvicorn[standard]"

This file has a stub GameState class so it runs standalone. Swap it for
your real game engine (the one you already built for the CLI version) —
everything else, the connection handling and message routing, stays the
same.
"""

from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

app = FastAPI()


# ---------------------------------------------------------------------------
# TODO: replace this with your real game engine, e.g.
#   from checkers.game import GameState
# It just needs an apply_move() and a to_dict() like the ones below.
# ---------------------------------------------------------------------------
class GameState:
    """Stand-in for your real game engine. Replace with your actual class."""

    def __init__(self):
        self.board = self._empty_board()
        self.turn = "player1"

    def _empty_board(self):
        # Placeholder 5x5 grid, not the real star-shaped board.
        # Swap in your actual board representation.
        return [[None for _ in range(5)] for _ in range(5)]

    def apply_move(self, player: str, move_from, move_to):
        """
        Validate and apply a move. Return (success, error_message).
        Replace the body with a call into your real validation/apply logic
        (including your super jump variant).
        """
        if player != self.turn:
            return False, "Not your turn"

        # TODO: real legality check goes here.
        self.board[move_to[0]][move_to[1]] = self.board[move_from[0]][move_from[1]]
        self.board[move_from[0]][move_from[1]] = None
        self.turn = "player2" if self.turn == "player1" else "player1"
        return True, None

    def to_dict(self):
        return {"board": self.board, "turn": self.turn}


class ConnectionManager:
    """Tracks which open sockets belong to which game room."""

    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {}
        self.games: Dict[str, GameState] = {}

    async def connect(self, game_id: str, websocket: WebSocket) -> str:
        await websocket.accept()
        self.rooms.setdefault(game_id, [])
        self.games.setdefault(game_id, GameState())

        # First person to join a room is player1, second is player2.
        player = "player1" if len(self.rooms[game_id]) == 0 else "player2"
        self.rooms[game_id].append(websocket)
        return player

    def disconnect(self, game_id: str, websocket: WebSocket):
        if game_id in self.rooms and websocket in self.rooms[game_id]:
            self.rooms[game_id].remove(websocket)
        if game_id in self.rooms and not self.rooms[game_id]:
            del self.rooms[game_id]
            del self.games[game_id]

    async def broadcast(self, game_id: str, message: dict):
        for connection in self.rooms.get(game_id, []):
            await connection.send_json(message)


manager = ConnectionManager()


@app.websocket("/ws/{game_id}")
async def game_socket(websocket: WebSocket, game_id: str):
    player = await manager.connect(game_id, websocket)

    # Tell this client which player they are.
    await websocket.send_json({"type": "player_assigned", "player": player})

    # Send the current board state to the newly joined player.
    game = manager.games[game_id]
    await websocket.send_json({"type": "state", **game.to_dict()})

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "move":
                success, error = game.apply_move(player, data["from"], data["to"])
                if success:
                    await manager.broadcast(game_id, {"type": "state", **game.to_dict()})
                else:
                    await websocket.send_json({"type": "error", "message": error})

    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)
        await manager.broadcast(game_id, {"type": "player_left", "player": player})


# Serve the frontend from the same app so you only need one deployment
# target. Put index.html (and any CSS/JS) in a "static" folder next to
# this file. Mounted last so it doesn't shadow the /ws route above.
app.mount("/", StaticFiles(directory="static", html=True), name="static")