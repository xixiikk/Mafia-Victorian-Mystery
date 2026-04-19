# app.py - С ПОДДЕРЖКОЙ АВАТАРОК ПО РОЛЯМ
import os
import uuid
import random
from enum import Enum
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import asyncio
from dotenv import load_dotenv

load_dotenv()

# ============ МОДЕЛИ ============
class CreateGameRequest(BaseModel):
    player_name: str

class VoteRequest(BaseModel):
    voter_name: str
    target_name: str

class NightActionRequest(BaseModel):
    player_name: str
    action_type: str
    target_name: str

class ChatRequest(BaseModel):
    player_name: str
    message: str

# ============ КОНСТАНТЫ ============
ROLE_MAFIA = "mafia"
ROLE_CIVILIAN = "civilian"
ROLE_COMMISSAR = "commissar"

# АВАТАРКИ ДЛЯ РАЗНЫХ РОЛЕЙ (ваши ссылки)
AVATARS = {
    "peaceful": "https://sun9-43.userapi.com/s/v1/ig2/4WTWB2vlCDVvkb1f4HZyt21lwnHUHy9IhZ420W7FEWRvTcpfBReZC-miNs3BXtgSQ8DuXNDT-0f7FXbEyiaHq5R9.jpg?quality=95&as=32x32,48x48,72x72,108x108,160x160,240x240,360x360,480x480,540x540,640x640,720x720,1024x1024&from=bu&u=wInRurBI8KXsT0JcK2nbdx5X_i7xSqhQHara0u3MPmQ&cs=1024x0",
    "mafia": "https://sun9-87.userapi.com/s/v1/ig2/1goCpcsrRhAqzdK6MFKslKva8omf_R1nFOLI8A4-iiXhfEnM5r6tASsG1gKYzVYTvPFQcPX63m7YA0ONbbHaDUwR.jpg?quality=95&as=32x32,48x48,72x72,108x108,160x160,240x240,360x360,480x480,540x540,640x640,720x720,1024x1024&from=bu&u=4QvZfCrLQxJf8J57f-GVQy7v6HQ7A4u_UHt7PQ95IsE&cs=1024x0"
}

# Имена и картинки для AI (постоянные, не зависят от роли)
AI_PLAYERS = [
    {"name": "Белла Свон", "image": "https://i.pinimg.com/736x/f6/37/d8/f637d8f1b8e5b6d3469a1732cf01a9d6.jpg"},
    {"name": "Эдвард Каллен", "image": "https://i.pinimg.com/736x/29/ea/b2/29eab279e0f3b811595728885b247343.jpg"},
    {"name": "Джейкоб Блэк", "image": "https://i.pinimg.com/736x/23/90/76/239076e4e42d49cfa8f2fb87c8479a29.jpg"},
    {"name": "Чарли Свон", "image": "https://i.pinimg.com/736x/5f/54/50/5f545089a86f2dbb1a2e395f0ef91c1e.jpg"},
]

DEFAULT_IMAGE = "https://i.pinimg.com/736x/f6/37/d8/f637d8f1b8e5b6d3469a1732cf01a9d6.jpg"

class Role(Enum):
    MAFIA = ROLE_MAFIA
    COMMISSAR = ROLE_COMMISSAR
    CIVILAN = ROLE_CIVILIAN

class Player:
    def __init__(self, name: str, role: Role, is_ai: bool = False, image: str = None):
        self.name = name
        self.role = role
        self.is_ai = is_ai
        self.alive = True
        self.image = image or DEFAULT_IMAGE

# ============ ЛОГИКА ИГРЫ ============

class MafiaGame:
    def __init__(self, players: List[Player], current_player_name: str):
        self.players = players
        self.current_player_name = current_player_name
        self.alive_players = [p for p in players if p.alive]
        self.current_phase = "day"
        self.day_votes = {}
        self.night_kill_target = None
        self.night_check_target = None
        self.last_night_victim = None
        self.last_executed = None
        self.day_count = 1
        self.winner = None
        self.chat_history = []
        
    def get_mafia_count(self) -> int:
        return sum(1 for p in self.alive_players if p.role == Role.MAFIA)
    
    def get_citizens_count(self) -> int:
        return sum(1 for p in self.alive_players if p.role in [Role.CIVILAN, Role.COMMISSAR])
    
    def get_player_role(self, player_name: str) -> Optional[str]:
        for p in self.players:
            if p.name == player_name:
                return p.role.value
        return None
    
    def check_winner(self) -> Optional[str]:
        mafia = self.get_mafia_count()
        citizens = self.get_citizens_count()
        
        if mafia == 0:
            return "citizens"
        if mafia >= citizens:
            return "mafia"
        return None
    
    def process_day_vote(self) -> Optional[str]:
        if not self.day_votes:
            return None
        
        vote_count = {}
        for target in self.day_votes.values():
            vote_count[target] = vote_count.get(target, 0) + 1
        
        max_votes = max(vote_count.values())
        candidates = [p for p, v in vote_count.items() if v == max_votes]
        
        if len(candidates) == 1:
            executed = candidates[0]
            for p in self.players:
                if p.name == executed:
                    p.alive = False
                    break
            self.alive_players = [p for p in self.alive_players if p.name != executed]
            self.last_executed = executed
            self.day_count += 1
            self.add_chat_message("Система", f"⚡ {executed} был казнён! Его роль: {self.get_player_role(executed)}")
            return executed
        return None
    
    def process_night(self):
        result = {"killed": None, "checked": None, "is_mafia": None}
        
        if self.night_check_target:
            for p in self.players:
                if p.name == self.night_check_target:
                    is_mafia = (p.role == Role.MAFIA)
                    result["checked"] = self.night_check_target
                    result["is_mafia"] = is_mafia
                    break
        
        if self.night_kill_target:
            for p in self.players:
                if p.name == self.night_kill_target:
                    p.alive = False
                    result["killed"] = self.night_kill_target
                    break
            self.alive_players = [p for p in self.alive_players if p.name != self.night_kill_target]
            self.last_night_victim = self.night_kill_target
            self.add_chat_message("Система", f"💀 {self.night_kill_target} был убит мафией!")
        
        self.night_kill_target = None
        self.night_check_target = None
        
        return result
    
    def add_chat_message(self, sender: str, message: str):
        self.chat_history.append(f"{sender}: {message}")
        if len(self.chat_history) > 100:
            self.chat_history = self.chat_history[-100:]
    
    def get_state(self) -> dict:
        current_player = next((p for p in self.players if p.name == self.current_player_name), None)
        
        role_in_russian = {
            "mafia": "Мафия",
            "commissar": "Комиссар",
            "civilian": "Мирный"
        }.get(current_player.role.value if current_player else "???", "???")
        
        players_for_display = []
        for p in self.alive_players:
            # Для реального игрока отправляем его роль, чтобы фронтенд выбрал правильную аватарку
            if p.name == self.current_player_name:
                player_role_for_avatar = p.role.value
            else:
                player_role_for_avatar = None  # Для AI и других игроков роль скрыта
            
            players_for_display.append({
                "name": p.name,
                "role_display": "???" if p.is_ai else role_in_russian,
                "role_for_avatar": player_role_for_avatar,  # Только для текущего игрока
                "isUser": p.name == self.current_player_name,
                "image": p.image,
                "alive": p.alive
            })
        
        can_act_at_night = False
        night_action_type = None
        if self.current_phase == "night" and current_player and current_player.alive:
            if current_player.role == Role.MAFIA:
                can_act_at_night = True
                night_action_type = "kill"
            elif current_player.role == Role.COMMISSAR:
                can_act_at_night = True
                night_action_type = "check"
        
        return {
            "phase": self.current_phase,
            "day": self.day_count,
            "players": players_for_display,
            "user_role": role_in_russian,
            "user_alive": current_player.alive if current_player else False,
            "winner": self.check_winner(),
            "chat_history": self.chat_history[-30:],
            "can_act_at_night": can_act_at_night,
            "night_action_type": night_action_type,
            "last_night_victim": self.last_night_victim,
            "last_executed": self.last_executed
        }

# ============ API СЕРВЕР ============

app = FastAPI(title="Mafia Game API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

games: Dict[str, MafiaGame] = {}
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# ============ СТАТИЧЕСКИЕ ФАЙЛЫ ============

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(CURRENT_DIR, "index.html"))

@app.get("/style.css")
async def serve_css():
    return FileResponse(os.path.join(CURRENT_DIR, "style.css"), media_type="text/css")

@app.get("/script.js")
async def serve_js():
    return FileResponse(os.path.join(CURRENT_DIR, "script.js"), media_type="application/javascript")

# ============ AI ПОВЕДЕНИЕ ============

def ai_vote(game: MafiaGame, ai_player: Player) -> str:
    alive_others = [p.name for p in game.alive_players if p.name != ai_player.name]
    if not alive_others:
        return None
    return random.choice(alive_others)

def ai_night_action(game: MafiaGame, ai_player: Player) -> dict:
    alive_others = [p.name for p in game.alive_players if p.name != ai_player.name]
    if not alive_others:
        return None
    
    if ai_player.role == Role.MAFIA:
        non_mafia = [p.name for p in game.alive_players if p.name != ai_player.name and p.role != Role.MAFIA]
        if non_mafia:
            return {"action": "kill", "target": random.choice(non_mafia)}
    elif ai_player.role == Role.COMMISSAR:
        return {"action": "check", "target": random.choice(alive_others)}
    return None

# ============ API ЭНДПОИНТЫ ============

@app.post("/game/create")
async def create_game(request: CreateGameRequest):
    player_name = request.player_name
    print(f"🎮 Создание игры для {player_name}")
    
    all_players = []
    roles = [Role.MAFIA, Role.COMMISSAR, Role.CIVILAN, Role.CIVILAN, Role.CIVILAN]
    random.shuffle(roles)
    
    real_player = Player(player_name, roles[0], is_ai=False)
    all_players.append(real_player)
    
    for i, ai_data in enumerate(AI_PLAYERS):
        ai_role = roles[i + 1]
        ai_player = Player(ai_data["name"], ai_role, is_ai=True, image=ai_data["image"])
        all_players.append(ai_player)
    
    game_id = str(uuid.uuid4())[:8]
    game = MafiaGame(all_players, player_name)
    games[game_id] = game
    
    game.add_chat_message("Система", f"🎭 Игра началась! Всего игроков: {len(all_players)}")
    for ai in all_players[1:]:
        game.add_chat_message(ai.name, f"Привет! Я {ai.name}.")
    
    role_in_russian = {
        Role.MAFIA: "Мафия",
        Role.COMMISSAR: "Комиссар",
        Role.CIVILAN: "Мирный"
    }[real_player.role]
    
    print(f"✅ Игра {game_id}: {player_name} - {role_in_russian}")
    
    return {
        "game_id": game_id,
        "user_role": role_in_russian,
        "user_role_raw": real_player.role.value,  # Отправляем raw роль для аватарки
        "players": [
            {
                "name": p.name, 
                "role_display": "???" if p.is_ai else role_in_russian,
                "role_raw": p.role.value if p.name == player_name else None,
                "isUser": p.name == player_name,
                "image": p.image
            }
            for p in all_players
        ]
    }

@app.post("/game/{game_id}/vote")
async def cast_vote(game_id: str, request: VoteRequest):
    if game_id not in games:
        raise HTTPException(404, "Game not found")
    
    game = games[game_id]
    if game.current_phase != "day":
        return {"status": "not_voting_phase", "error": "Сейчас не день"}
    
    game.day_votes[request.voter_name] = request.target_name
    game.add_chat_message(request.voter_name, f"Голосует за {request.target_name}")
    
    alive_names = [p.name for p in game.alive_players]
    
    for player in game.alive_players:
        if player.is_ai and player.name not in game.day_votes:
            ai_choice = ai_vote(game, player)
            if ai_choice:
                game.day_votes[player.name] = ai_choice
                game.add_chat_message(player.name, f"Голосует за {ai_choice}")
    
    if len(game.day_votes) >= len(alive_names):
        executed = game.process_day_vote()
        winner = game.check_winner()
        
        if winner:
            game.winner = winner
            game.current_phase = "ended"
            game.add_chat_message("Система", f"🏆 ИГРА ОКОНЧЕНА! Победили: {'Мафия' if winner == 'mafia' else 'Мирные'}!")
            return {"status": "game_ended", "winner": winner, "executed": executed}
        
        game.current_phase = "night"
        game.day_votes = {}
        
        for player in game.alive_players:
            if player.is_ai:
                action = ai_night_action(game, player)
                if action:
                    if action["action"] == "kill" and not game.night_kill_target:
                        game.night_kill_target = action["target"]
                    elif action["action"] == "check" and not game.night_check_target:
                        game.night_check_target = action["target"]
        
        return {"status": "night_phase", "executed": executed}
    
    return {"status": "vote_recorded", "votes_received": len(game.day_votes), "total_players": len(alive_names)}

@app.post("/game/{game_id}/night_action")
async def night_action(game_id: str, request: NightActionRequest):
    if game_id not in games:
        raise HTTPException(404, "Game not found")
    
    game = games[game_id]
    if game.current_phase != "night":
        return {"status": "not_night_phase", "error": "Сейчас не ночь"}
    
    player = next((p for p in game.players if p.name == request.player_name), None)
    if not player or not player.alive:
        return {"status": "error", "error": "Вы мертвы"}
    
    if request.action_type == "kill" and player.role != Role.MAFIA:
        return {"status": "error", "error": "Только мафия может убивать"}
    if request.action_type == "check" and player.role != Role.COMMISSAR:
        return {"status": "error", "error": "Только комиссар может проверять"}
    
    if request.action_type == "kill":
        game.night_kill_target = request.target_name
        game.add_chat_message(player.name, f"🔪 Выбирает жертву...")
    elif request.action_type == "check":
        game.night_check_target = request.target_name
        game.add_chat_message(player.name, f"🔍 Решает проверить {request.target_name}")
    
    mafia_alive = [p for p in game.alive_players if p.role == Role.MAFIA]
    commissar_alive = [p for p in game.alive_players if p.role == Role.COMMISSAR]
    
    actions_done = 0
    if game.night_kill_target:
        actions_done += 1
    if game.night_check_target:
        actions_done += 1
    
    expected_actions = (1 if mafia_alive else 0) + (1 if commissar_alive else 0)
    
    if actions_done >= expected_actions or len(game.alive_players) <= 2:
        night_result = game.process_night()
        winner = game.check_winner()
        
        if winner:
            game.winner = winner
            game.current_phase = "ended"
            game.add_chat_message("Система", f"🏆 ИГРА ОКОНЧЕНА! Победили: {'Мафия' if winner == 'mafia' else 'Мирные'}!")
            return {"status": "game_ended", "winner": winner, "night_result": night_result}
        
        game.current_phase = "day"
        
        check_result = None
        if night_result.get("checked"):
            check_result = {
                "target": night_result["checked"],
                "is_mafia": night_result["is_mafia"]
            }
        
        return {"status": "day_phase", "night_result": night_result, "check_result": check_result}
    
    return {"status": "waiting_for_actions", "actions_done": actions_done, "expected": expected_actions}

@app.get("/game/{game_id}/state")
async def get_game_state(game_id: str):
    if game_id not in games:
        raise HTTPException(404, "Game not found")
    
    game = games[game_id]
    return game.get_state()

@app.post("/game/{game_id}/chat")
async def send_chat_message(game_id: str, request: ChatRequest):
    if game_id not in games:
        raise HTTPException(404, "Game not found")
    
    game = games[game_id]
    game.add_chat_message(request.player_name, request.message)
    return {"status": "message_sent"}

@app.post("/game/{game_id}/next_phase")
async def next_phase(game_id: str):
    if game_id not in games:
        raise HTTPException(404, "Game not found")
    
    game = games[game_id]
    
    if game.current_phase == "day":
        game.current_phase = "night"
        game.day_votes = {}
        return {"status": "night_phase"}
    elif game.current_phase == "night":
        night_result = game.process_night()
        winner = game.check_winner()
        if winner:
            game.winner = winner
            game.current_phase = "ended"
            return {"status": "game_ended", "winner": winner}
        game.current_phase = "day"
        return {"status": "day_phase"}
    else:
        return {"status": "game_ended", "winner": game.winner}

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 ЗАПУСК ИГРЫ МАФИЯ")
    print("=" * 50)
    print(f"🌐 Сервер: http://localhost:3000")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=3000)