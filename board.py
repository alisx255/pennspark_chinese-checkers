from builtins import ValueError
import json

#TODO:
#each players has number of pieces
#player chooses where to play
from enum import Enum


class Direction(Enum):
    E = (1, 0, -1)
    NE = (1, -1, 0)
    SE = (0, 1, -1)
    W = (-1, 0, 1)
    SW = (-1, 1, 0)
    NW = (0, -1, 1)

class GameState:
    def __init__(self):
        self.numberPlayers = 0
        self.currentPlayer = 0
        self.superJumpActive = False
        self.gameActive = False
        self.gameDone = False
        self.board = {} #dict of the board, coords -> what piece is on it
        self.pieces = {} #dict of the player -> list of pieces coords
        self.corners = {} #dict of coords -> which corner it is in
        self.players = {} #dict of players -> if they are done
        self.playerCorner = {} # dict of player -> which corner theyre in
        self.finishOrder = [] #list of finish order
        self.history = [] #list of history...
        self.generateValidPositions()
        #board: -1 is empty, 0-5 is player values

#helpers
    def axialToCube(self, a):
        q, r = a
        x = q
        z = r
        y = -x - z
        return (x, y, z)

    def cubeToAxial(self, a):
        x, y, z = a
        q = x
        r = z
        return (q, r)

    def rotate60(self, pos):
        i, j = pos
        return (-j, i+j)

    def addCoords(self, a, b):
        return tuple(x + y for x, y in zip(a, b))
    
    def generateValidPositions(self):
        #make the hexagon and worry about the triangles later
        for i in range(9):
            for j in range(9):
                key = (i-4, j-4)
                x, y = key
                if -x - y < 5 and -x - y > -5:
                    self.board[key] = -1
        self.generateCorner()

    def generateCorner(self):
        for i in range(-5, -9, -1):
            for j in range (-4-i, 5, 1):
                key = (i, j)
                r = 0
                for r in range(6):
                    self.corners[key] = r
                    self.board[key] = -1
                    key = self.rotate60(key)
    def unfillCorner(self, player):
        if player not in self.pieces:
            raise ValueError("Player has no corner to remove")
        for key in self.pieces[player]:
            self.board[key] = -1
        del self.pieces[player]
                    
    def goalCorner(self, player):
        return (self.playerCorner[player] + 3) % 6

# corner can be 0-5
    def fillCorner(self, corner, player):
        positions = []
        for i in range(-5, -9, -1):
            for j in range(-4-i, 5, 1):
                key = (i, j)
                for _ in range(corner):
                    key = self.rotate60(key)
                positions.append(key)

        if any(self.board[key] != -1 for key in positions):
            raise ValueError("Corner already occupied")

        for key in positions:
            self.board[key] = player
        self.pieces[player] = set(positions)

    def checkCornerDone(self, player):
        goal = self.goalCorner(player)
        positions = []
        for i in range(-5, -9, -1):
            for j in range (-4-i, 5, 1):
                key = (i, j) 
                for _ in range(goal):
                    key = self.rotate60(key)
                positions.append(key)
        return all(self.board[key] == player for key in positions)
  
    def isValidPosition(self, a):
        if a in self.board:
            return True
        return False

    def isBlockedPosition(self, a):
        q, r = a
        if not self.isValidPosition(a):
            return True
        if self.board[(q, r)] == -1:
            return False
        return True   

    def playerFinished(self, player):
        self.players[player] = True
        self.finishOrder.append(player)

    def getFinishOrder(self, player):
        for i in range(len(self.finishOrder)):
            if self.finishOrder[i] == player:
                return i
            
    def gameFinished(self):
        self.gameActive = False
        self.gameDone = True
        pass

    # =================== MOVES ===================
    def move(self, q, r, direction: Direction):
        t = self.axialToCube((q, r))
        a = self.addCoords(t, direction.value)
        a_axial = self.cubeToAxial(a)
        if (not self.isValidPosition(a_axial)):
            return None
        if (self.isBlockedPosition(a_axial)):
            return None
        return a_axial

    def jump(self, q, r, direction, isSuper):
        if (isSuper):
            return self.superJump(q, r, direction)
        else:
            return self.singleJump(q, r, direction)

    def singleJump(self, q, r, direction: Direction):
        t = self.axialToCube((q, r))
        b = self.addCoords(t, direction.value)
        b_axial = self.cubeToAxial(b)
        if (not self.isValidPosition(b_axial)):
            return None
        if (not self.isBlockedPosition(b_axial)):
            return None
        a = self.addCoords(b, direction.value)
        a_axial = self.cubeToAxial(a)
        if (not self.isValidPosition(a_axial)):
            return None
        if (self.isBlockedPosition(a_axial)):
            return None
        return a_axial

    def superJump(self, q, r, direction: Direction):
        a = self.axialToCube((q, r))
        canJump = True
        block = False
        counter = 0
        while (canJump):
            a = self.addCoords(a, direction.value)
            a_axial = self.cubeToAxial(a)
            if (not self.isValidPosition(a_axial)):
                canJump = False
            counter = counter + 1
            if (self.isBlockedPosition(a_axial)):
                block = True
                break
        while block == True and counter > 0:
            a = self.addCoords(a, direction.value)
            a_axial = self.cubeToAxial(a)
            if (self.isBlockedPosition(a_axial) or not self.isValidPosition(a_axial)):
                counter = 0
                canJump = False
                break
            counter = counter - 1
        if canJump and block and counter == 0:
            return a_axial
        return None

    def isSpoiling(self, q1, r1, q2, r2, player):
        if (q2, r2) in self.corners:
            if self.corners[(q2, r2)] == self.goalCorner(player):
                return False
            if self.corners[(q2, r2)] == self.playerCorner[player]:
                if (q1, r1) in self.corners:
                    if self.corners[(q1, r1)] == self.playerCorner[player]:
                        return False
            return True
        return False
    
    def dfsHelper(self, q, r, visited, player):
        if not self.isValidPosition((q, r)):
            return
        for direction in Direction:
            t1 = self.move(q, r, direction)
            if t1 is not None:
                if t1 not in visited:
                    q1, r1 = t1
                    if not self.isSpoiling(q, r, q1, r1, player):
                        visited.add(t1)

    def dfsHelper2(self, q, r, visited, player):
        if not self.isValidPosition((q, r)):
            return
        for direction in Direction:
            t2 = self.jump(q, r, direction, self.superJumpActive)
            if t2 is not None:
                if t2 not in visited:
                    q2, r2 = t2
                    if not self.isSpoiling(q, r, q2, r2, player):
                        visited.add(t2)
                    self.dfsHelper2(q2, r2, visited, player)
        
    def findLegalMoves(self, q, r):
        visited = set()
        if not self.isValidPosition((q, r)):
            return visited
        player = self.board[(q, r)]
        self.dfsHelper(q, r, visited, player)
        self.dfsHelper2(q, r, visited, player)
        return visited

    def findAllMoves(self, player):
        visited = {}
        a = self.pieces[player] 
        for i in a:
            q, r = i
            visited1 = self.findLegalMoves(q, r)
            visited[(q, r)] = visited1
        return visited

    def applyMove(self, q1, r1, q2, r2, player):
        old = (q1, r1)
        if not self.isValidPosition(old):
            raise ValueError("Invalid position")
        piece = self.board[old]
        new = (q2, r2)
        if player != self.currentPlayer:
            raise ValueError("Not your turn")
        if player != piece:
            raise ValueError("Must move your own piece")
        if player == piece and player == self.currentPlayer:
            if new in self.findLegalMoves(q1, r1):
                record = {"old": old, "new": new, "player": player, "prevPlayer": self.currentPlayer, "finished": False,}
                self.board[old] = -1  
                self.board[new] = player
                self.pieces[player].discard(old)
                self.pieces[player].add(new)    
                done = self.checkCornerDone(player)
                if done:
                    self.playerFinished(player)
                    record["finished"] = True
                self.advanceTurn()
                self.history.append(record)
            else:
                raise ValueError("Illegal move")

    def advanceTurn(self):
        t = self.currentPlayer 
        self.currentPlayer = (self.currentPlayer + 1) % self.numberPlayers
        while (self.isPlayerFinished(self.currentPlayer)):
            self.currentPlayer = (self.currentPlayer + 1) % self.numberPlayers
        if self.currentPlayer == t:
            self.gameFinished()

    def undoMove(self):
        if not self.history:
            raise ValueError("no moves have been played!")
        record = self.history.pop()
        old = record["old"]
        new = record["new"]
        player = record["player"]
        newPlayer = record["prevPlayer"]
        finished = record["finished"]
        if finished:
            self.players[player] = False
            self.finishOrder.pop()
        self.board[old] = player
        self.board[new] = -1
        self.pieces[player].discard(new)
        self.pieces[player].add(old)
        self.currentPlayer = newPlayer

    # =================== PLAYERS ===================== 

    def registerPlayer(self):
        if self.gameActive:
            raise ValueError("Game already started")
        player = self.numberPlayers
        self.players[player] = False        # finished = False
        self.playerCorner[player] = None    # not seated yet
        self.numberPlayers += 1
        return player
    def chooseCorner(self, player, corner):
        if self.gameActive:
            raise ValueError("game already started")
        if player not in self.players:
            raise ValueError("unknown player")
        if corner in self.playerCorner.values():
            raise ValueError("corner already occupied")
        if self.playerCorner[player] is not None:
            self.unfillCorner(player)
        self.fillCorner(corner, player)
        self.playerCorner[player] = corner

    def leaveCorner(self, player):
        if player not in self.players:
            raise ValueError("Unknown player")
        if self.playerCorner[player] is None:
            raise ValueError("player has no corner")
        self.unfillCorner(player)
        self.playerCorner[player] = None

    def isPlayerFinished(self, player):
        return self.players[player]

    def startGame(self):
        if self.numberPlayers < 2:
            raise ValueError("not enough players")
        if not all(c is not None for c in self.playerCorner.values()):
            raise ValueError("not all players have chosen a corner")
        self.gameActive = True

    def saveGame(self, filepath):
        with open(filepath, "w") as f:
            json.dump(self.toDict(), f)

    def toDict(self):
        return {
            "numberPlayers": self.numberPlayers,
            "currentPlayer": self.currentPlayer,
            "superJumpActive": self.superJumpActive,
            "gameActive": self.gameActive,
            "gameDone": self.gameDone,

            "board": {f"{q},{r}": v for (q, r), v in self.board.items()}, #dict of the board, coords -> what piece is on it
            "pieces": {v: [f"{q},{r}" for q, r in s] for v, s in self.pieces.items()}, #dict of the player -> list of pieces coords
            "corners": {f"{q},{r}": v for (q, r), v in self.corners.items()}, #dict of coords -> which corner it is in

            "players": self.players, #dict of players -> if they are done
            "playerCorner": self.playerCorner, # dict of player -> which corner theyre in
            "finishOrder": self.finishOrder, #list of finish order

            "history": [
                {
                    'old': f"{r['old'][0]},{r['old'][1]}",
                    'new': f"{r['new'][0]},{r['new'][1]}",
                    'player': r["player"],
                    'prevPlayer': r["prevPlayer"],
                    'finished': r["finished"],
                } 
                for r in self.history
            ], 
        }
    
    @staticmethod
    def loadFromDict(dict):
        gs = GameState()
        gs.numberPlayers = dict["numberPlayers"]
        gs.currentPlayer = dict["currentPlayer"]
        gs.superJumpActive = dict["superJumpActive"]
        gs.gameActive = dict["gameActive"]
        gs.gameDone = dict["gameDone"]

        def parseKey(s):
            q, r = s.split(",")
            return (int(q), int(r))
        
        gs.board = {parseKey(s): v for s, v in dict["board"].items()}
        gs.pieces = {int(p): {parseKey(s) for s in positions} for p, positions in dict["pieces"].items()}
        gs.corners = {parseKey(s): v for s, v in dict["corners"].items()}

        gs.players = {int(p): finished for p, finished in dict["players"].items()}
        gs.playerCorner = {int(p): c for p, c in dict["playerCorner"].items()}
        gs.finishOrder = dict["finishOrder"]
        gs.history = [
            {
                'old': parseKey(r["old"]),
                'new': parseKey(r["new"]),
                'player': r["player"],
                'prevPlayer': r["prevPlayer"],
                'finished': r["finished"],
            }
            for r in dict["history"]
            ]

        return gs



    


    
    
if __name__ == "__main__":
    gs = GameState()
    print(len(gs.board))     # how many valid cells total
    print(len(gs.corners))   # should be 60 (6 corners × 10 cells each)
    p0 = gs.registerPlayer()
    p1 = gs.registerPlayer()
    gs.chooseCorner(p0, 0)
    gs.chooseCorner(p1, 3)
    gs.startGame()
    
    print(gs.currentPlayer)          # expect 0
    print(gs.board[(-6,4)])          # expect 0 (player 0's piece)
    print(gs.board[(-4,2)])          # expect -1 (empty)

    gs.applyMove(-6, 4, -4, 2, p0)

    print(gs.board[(-6,4)])          # expect -1 now
    print(gs.board[(-4,2)])          # expect 0 now
    print(gs.currentPlayer)          # expect 1 (turn advanced)
    print((-6,4) in gs.pieces[p0])   # expect False
    print((-4,2) in gs.pieces[p0])   # expect True




    try:
        gs.applyMove(-4, 2, -6, 4, p0)   # p0 tries to move again, but it's p1's turn now
    except ValueError as e:
        print("correctly rejected:", e)

    try:
        gs.applyMove(0, 0, 0, 1, p1)     # illegal/nonsense move
    except ValueError as e:
        print("correctly rejected:", e)

    gs2 = GameState()
    try:
        gs2.startGame()
    except ValueError as e:
        print("correctly rejected:", e)   # "Not enough players"

    p0 = gs2.registerPlayer()
    p1 = gs2.registerPlayer()
    try:
        gs2.startGame()
    except ValueError as e:
        print("correctly rejected:", e)   # "Not all players have chosen a corner"

    gs.saveGame("test_save.json")
    import json
    with open("test_save.json") as f:
        loaded_dict = json.load(f)
    gs3 = GameState.loadFromDict(loaded_dict)

    assert gs3.board == gs.board
    assert gs3.corners == gs.corners
    assert gs3.pieces == gs.pieces
    assert gs3.currentPlayer == gs.currentPlayer
    assert gs3.history == gs.history
    print("save/load round-trip OK")

