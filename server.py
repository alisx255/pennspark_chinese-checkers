from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import json
from board import GameState  # your file, adjust the import name to match
import db
import auth

app = FastAPI()

db.init_db()

SESSION_COOKIE = "session_token"


def get_logged_in_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    return auth.get_username(token)

# Resume a saved game if one exists (server restart), otherwise start fresh.
saved_state = db.load_game_state()
if saved_state is not None:
    gs = GameState.loadFromDict(saved_state)
else:
    gs = GameState()
    p0 = gs.registerPlayer()
    p1 = gs.registerPlayer()
    gs.chooseCorner(p0, 0)
    gs.chooseCorner(p1, 3)
    gs.startGame()
    db.save_game_state(gs.toDict())

# Single hotseat mode: one tab controls both players, so there's no
# per-connection player assignment. board.py's applyMove already checks
# whose turn it is and that you're moving your own piece.
connections = []


def board_state_message() -> str:
    """Current board + whose turn it is, in the shape the frontend expects."""
    board = {f"{q},{r}": v for (q, r), v in gs.board.items()}
    return json.dumps({
        "type": "update",
        "board": board,
        "currentPlayer": gs.currentPlayer,
    })


async def broadcast(message: str):
    for conn in list(connections):
        await conn.send_text(message)


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    with open("static/login.html") as f:
        return f.read()


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if auth.authenticate(username, password):
        token = auth.create_session(username)
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
        return response
    return RedirectResponse(url="/login?error=1", status_code=303)


@app.get("/register", response_class=HTMLResponse)
async def register_page():
    with open("static/register.html") as f:
        return f.read()


@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...)):
    if auth.register_user(username, password):
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/register?error=1", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    auth.destroy_session(request.cookies.get(SESSION_COOKIE))
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Reject before accept()ing if there's no valid session cookie, so an
    # unauthenticated client never gets a live connection to the game.
    username = auth.get_username(websocket.cookies.get(SESSION_COOKIE))
    if username is None:
        await websocket.close(code=1008)  # 1008 = policy violation
        return

    await websocket.accept()
    connections.append(websocket)
    await websocket.send_text(board_state_message())

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
                msg_type = data.get("type")
            except (json.JSONDecodeError, AttributeError):
                await websocket.send_text(json.dumps({"type": "error", "message": "Malformed message"}))
                continue

            if msg_type == "legal_moves":
                try:
                    q, r = data["position"]
                except (KeyError, ValueError, TypeError):
                    await websocket.send_text(json.dumps({"type": "error", "message": "Malformed position"}))
                    continue

                try:
                    moves = gs.findLegalMoves(q, r)
                except Exception:
                    moves = set()

                await websocket.send_text(json.dumps({
                    "type": "legal_moves",
                    "position": [q, r],
                    "moves": [list(m) for m in moves],
                }))
                continue

            if msg_type == "move":
                try:
                    move_from = data["from"]
                    move_to = data["to"]
                    move_player = data["player"]
                except (KeyError, TypeError):
                    await websocket.send_text(json.dumps({"type": "error", "message": "Malformed move"}))
                    continue

                try:
                    gs.applyMove(move_from[0], move_from[1], move_to[0], move_to[1], move_player)
                    db.save_game_state(gs.toDict())
                    db.log_move(move_player, move_from, move_to, username=username)
                    await broadcast(board_state_message())
                except ValueError as e:
                    await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
                continue

            await websocket.send_text(json.dumps({"type": "error", "message": f"Unknown message type: {msg_type}"}))

    except WebSocketDisconnect:
        connections.remove(websocket)


@app.get("/history")
async def history():
    """Recent moves pulled from the database. Useful for confirming
    persistence is actually working, and covers 'API calls' + 'database
    integration' together."""
    return db.get_move_history()


# Serve the frontend from the same app so you only need one deployment
# target. An explicit route (instead of app.mount at "/") means there's no
# ambiguity about it ever claiming the /ws path, regardless of where this
# line sits in the file.
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    username = get_logged_in_user(request)
    if username is None:
        return RedirectResponse(url="/login", status_code=303)
    with open("static/index.html") as f:
        html = f.read()
    return html.replace("{{USERNAME}}", username)