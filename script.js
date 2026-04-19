// script.js
let currentGameId = null;
let currentPlayerName = "";
let updateInterval = null;

async function startGame() {
    const nameInput = document.getElementById('player-name');
    const name = nameInput.value.trim();

    if (!name) {
        alert("Пожалуйста, представьтесь!");
        return;
    }
    
    currentPlayerName = name;

    try {
        const response = await fetch('/game/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player_name: name })
        });

        const data = await response.json();
        
        if (!response.ok) {
            alert("Ошибка: " + JSON.stringify(data));
            return;
        }
        
        currentGameId = data.game_id;

        document.getElementById('lobby').style.display = 'none';
        document.getElementById('game-table').style.display = 'block';
        document.getElementById('user-role-display').innerHTML = `🎭 Ваша роль: <span style="color:#f1d88a">${data.user_role}</span>`;
        
        addLogMessage("Система", `${name} заходит в зал. Двери закрываются...`);

        updateUI(data.players);
        
        // Запускаем обновление состояния каждые 2 секунды
        if (updateInterval) clearInterval(updateInterval);
        updateInterval = setInterval(updateGameState, 2000);
        setTimeout(updateGameState, 500);

    } catch (error) {
        console.error("Ошибка:", error);
        alert("Сервер не отвечает. Проверьте, запущен ли сервер!");
    }
}

function updateUI(players) {
    const playersList = document.getElementById('players-list');
    if (!playersList) return;
    
    playersList.innerHTML = ''; 
    
    players.forEach(player => {
        if (player.alive === false) return; // Показываем только живых
        
        const card = document.createElement('div');
        card.className = 'player-card';
        card.onclick = () => {
            if (document.getElementById('game-phase-indicator').innerText.includes("День")) {
                castVote(player.name);
            } else if (document.getElementById('game-phase-indicator').innerText.includes("Ночь")) {
                showNightActionMenu(player.name);
            }
        };
        card.innerHTML = `
            <div class="portrait" style="background-image: url('${player.image || 'https://i.pinimg.com/736x/f6/37/d8/f637d8f1b8e5b6d3469a1732cf01a9d6.jpg'}'); background-size: cover; background-position: center; height: 120px; border: 1px solid #bc9b6a; border-radius: 5px;"></div>
            <b>${player.name} ${player.isUser ? "(Вы)" : ""}</b>
            <p class="role-secret" style="color: #bc9b6a; font-size: 0.8em;">${player.role}</p>
        `;
        playersList.appendChild(card);
    });
}

function showNightActionMenu(targetName) {
    // Определяем, какое действие доступно
    fetch(`/game/${currentGameId}/state`)
        .then(res => res.json())
        .then(state => {
            if (state.can_act_at_night) {
                const actionType = state.night_action_type;
                const actionName = actionType === "kill" ? "убить" : "проверить";
                if (confirm(`Вы хотите ${actionName} ${targetName}?`)) {
                    performNightAction(actionType, targetName);
                }
            } else {
                alert("Вы не можете совершать ночные действия (вы не мафия и не комиссар, или уже сделали ход)");
            }
        });
}

async function performNightAction(actionType, targetName) {
    try {
        const response = await fetch(`/game/${currentGameId}/night_action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                player_name: currentPlayerName,
                action_type: actionType,
                target_name: targetName
            })
        });
        const result = await response.json();
        
        if
        (result.status === "day_phase") {
            addLogMessage("Система", "🌅 Наступает новый день");
            if (result.check_result && result.check_result.is_mafia) {
                addLogMessage("Комиссар", `🔍 ${result.check_result.target} - МАФИЯ!`);
            } else if (result.check_result && !result.check_result.is_mafia) {
                addLogMessage("Комиссар", `🔍 ${result.check_result.target} - мирный житель`);
            }
            if (result.night_result?.killed) {
                addLogMessage("Система", `💀 ${result.night_result.killed} был убит мафией!`);
            }
            document.getElementById('phase-btn').innerText = "Завершить обсуждение";
        } else if (result.status === "waiting_for_actions") {
            addLogMessage("Система", `⏳ Ожидание действий других игроков...`);
        } else if (result.status === "game_ended") {
            addLogMessage("Система", `🏆 ИГРА ОКОНЧЕНА! Победили: ${result.winner === "mafia" ? "Мафия" : "Мирные"}!`);
        }
        
        updateGameState();
    } catch (e) {
        console.error("Ошибка ночного действия:", e);
    }
}

async function castVote(targetName) {
    if (!currentGameId) {
        alert("Игра не создана!");
        return;
    }
    
    if (targetName === currentPlayerName) {
        alert("Нельзя голосовать за себя!");
        return;
    }

    try {
        const response = await fetch(`/game/${currentGameId}/vote`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                voter_name: currentPlayerName, 
                target_name: targetName 
            })
        });
        const result = await response.json();
        
        if (result.status === "night_phase") {
            addLogMessage("Система", "🌙 Наступает ночь...");
            if (result.executed) {
                addLogMessage("Система", `⚡ ${result.executed} был казнён!`);
            }
            document.getElementById('phase-btn').innerText = "Завершить ночь";
        } else if (result.status === "game_ended") {
            addLogMessage("Система", `🏆 ИГРА ОКОНЧЕНА! Победили: ${result.winner === "mafia" ? "Мафия" : "Мирные"}!`);
        } else if (result.status === "vote_recorded") {
            addLogMessage("Система", `✅ Ваш голос за ${targetName} учтён (${result.votes_received}/${result.total_players})`);
        }
        
        updateGameState();
    } catch (e) {
        console.error("Ошибка при голосовании", e);
    }
}

function addLogMessage(sender, text) {
    const log = document.getElementById('log-content');
    if (!log) return;
    log.innerHTML += `<p><b>[${sender}]:</b> ${text}</p>`;
    log.scrollTop = log.scrollHeight;
}

function sendMessage() {
    const input = document.getElementById('chat-input');
    if (input.value.trim() && currentGameId) {
        addLogMessage(currentPlayerName, input.value);
        
        fetch(`/game/${currentGameId}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                player_name: currentPlayerName, 
                message: input.value 
            })
        }).catch(e => console.error(e));
        
        input.value = "";
    }
}

async function updateGameState() {
    if (!currentGameId) return;
    try {
        const response = await fetch(`/game/${currentGameId}/state`);
        const state = await response.json();
        
        const phaseNames = { "day": "День", "night": "Ночь", "ended": "Игра завершена" };
        const phaseIndicator = document.getElementById('game-phase-indicator');
        if (phaseIndicator) {
            phaseIndicator.innerHTML = `${phaseNames[state.phase] || state.phase} ${state.day}`;
        }
        
        if (state.players) {
            updateUI(state.players);
        }
        
        // Обновляем кнопку в зависимости от фазы
        const phaseBtn = document.getElementById('phase-btn');
        if (state.phase === "day") {
            phaseBtn.innerText = "Завершить обсуждение";
            phaseBtn.onclick = () => nextPhase();
        } else if (state.phase === "night") {
            phaseBtn.innerText = "Завершить ночь";
            phaseBtn.onclick = () => nextPhase();
        }
        
        // Обновляем чат
        if (state.chat_history && state.chat_history.length > 0) {
            const log = document.getElementById('log-content');
            const currentLogText = log.innerText;
            const newMessages = state.chat_history.slice(-5);
            // Просто добавляем новые сообщения
            if (log.children.length !== state.chat_history.length + 1) {
                log.innerHTML = '<p><b>Система:</b> Город готовится к встрече с вами...</p>';
                state.chat_history.forEach(msg => {
                    const parts = msg.split(": ");
                    const sender = parts[0];
                    const text = parts.slice(1).join(": ");
                    log.innerHTML += `<p><b>[${sender}]:</b> ${text}</p>`;
                });
                log.scrollTop = log.scrollHeight;
            }
        }
        
        if (state.winner) {
            addLogMessage("Система", `🏆 ПОБЕДА! ${state.winner === "mafia" ? "Мафия захватила город" : "Мирные восстановили порядок"}!`);
            if (updateInterval) clearInterval(updateInterval);
        }
        
        // Если игрок умер
        if (!state.user_alive && state.user_alive !== undefined) {
            addLogMessage("Система", "💀 Вы погибли... Но можете наблюдать за игрой как зритель");
        }
        
    } catch (e) {
        console.log("Ошибка получения состояния:", e);
    }
}

async function nextPhase() {
    if (!currentGameId) return;
    
    try {
        const response = await fetch(`/game/${currentGameId}/next_phase`, {
            method: 'POST'
        });
        const result = await response.json();
        
        if (result.status === "night_phase") {
            addLogMessage("Система", "🌙 Наступает ночь...");
        } else if (result.status === "day_phase") {
            addLogMessage("Система", "☀️ Наступает новый день");
        } else if (result.status === "game_ended") {
            addLogMessage("Система", `🏆 ИГРА ОКОНЧЕНА! Победили: ${result.winner === "mafia" ? "Мафия" : "Мирные"}!`);
        }
        
        updateGameState();
    } catch (e) {
        console.error("Ошибка при смене фазы", e);
    }
}

document.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && document.getElementById('game-table').style.display !== 'none') {
        if (document.activeElement?.id === 'chat-input') {
            sendMessage();
        }
    }
});
