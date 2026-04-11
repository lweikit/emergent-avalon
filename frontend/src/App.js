import React, { useState, useEffect, useRef } from "react";
import "./App.css";
import axios from "axios";

// Environment variable access compatible with React 19 and craco
const getBackendUrl = () => {
  // Try runtime env injection (docker-entrypoint.sh sets window._env_)
  if (
    typeof window !== "undefined" &&
    window._env_ &&
    window._env_.REACT_APP_BACKEND_URL
  ) {
    return window._env_.REACT_APP_BACKEND_URL;
  }
  // Try build-time env (CRA bakes process.env.REACT_APP_* at build)
  if (typeof process !== "undefined" && process.env && process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  // Same-origin mode: empty string means use relative URLs (nginx proxies /api to backend)
  return "";
};

const getWsBaseUrl = () => {
  const backendUrl = getBackendUrl();
  if (backendUrl) {
    // Explicit backend URL — convert protocol
    return backendUrl.replace("https://", "wss://").replace("http://", "ws://");
  }
  // Same-origin mode: derive WS URL from current page location
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
};

const ROLE_DESCRIPTIONS = {
  merlin:
    "You can see all evil players except Mordred. Guide the good team to victory, but stay hidden from the Assassin.",
  percival:
    "You can see Merlin and Morgana, but don't know which is which. Protect Merlin while following their guidance.",
  loyal_servant:
    "You are a loyal servant of Arthur. Trust in Merlin's guidance and help complete missions.",
  morgana:
    "You appear as Merlin to Percival. Use this to confuse the good team while working with evil.",
  assassin:
    "You can see other evil players. If good wins, you can assassinate Merlin to win the game for evil.",
  mordred:
    "You are hidden from Merlin. Use this advantage to infiltrate missions and lead evil to victory.",
  oberon:
    "You are hidden from everyone. Work alone to sabotage missions without being detected.",
  minion:
    "You can see other evil players. Work together to sabotage missions and achieve evil victory.",
};

const MISSION_CONFIGS = {
  5: [
    [2, 1],
    [3, 1],
    [2, 1],
    [3, 1],
    [3, 1],
  ],
  6: [
    [2, 1],
    [3, 1],
    [4, 1],
    [3, 1],
    [4, 1],
  ],
  7: [
    [2, 1],
    [3, 1],
    [3, 1],
    [4, 2],
    [4, 1],
  ],
  8: [
    [3, 1],
    [4, 1],
    [4, 1],
    [5, 2],
    [5, 1],
  ],
  9: [
    [3, 1],
    [4, 1],
    [4, 1],
    [5, 2],
    [5, 1],
  ],
  10: [
    [3, 1],
    [4, 1],
    [4, 1],
    [5, 2],
    [5, 1],
  ],
};

function App() {
  const [backendUrl, setBackendUrl] = useState(getBackendUrl());
  const [apiUrl, setApiUrl] = useState(`${getBackendUrl()}/api`);
  const [wsBaseUrl, setWsBaseUrl] = useState(getWsBaseUrl());

  const [gameState, setGameState] = useState(null);
  const [playerId, setPlayerId] = useState(null);
  const [playerToken, setPlayerToken] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [playerName, setPlayerName] = useState("");
  const [sessionName, setSessionName] = useState("");
  const [sessionIdInput, setSessionIdInput] = useState("");
  const [joinAsSpectator, setJoinAsSpectator] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState([]);
  const [ladyTarget, setLadyTarget] = useState("");
  const [assassinTarget, setAssassinTarget] = useState("");
  const [ladyResult, setLadyResult] = useState(null);
  const [showLadyResult, setShowLadyResult] = useState(false);
  const [showEndGameConfirm, setShowEndGameConfirm] = useState(false);
  const [showVoteHistory, setShowVoteHistory] = useState(false);
  const [showGameLog, setShowGameLog] = useState(false);
  const [error, setError] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [wsRetryCount, setWsRetryCount] = useState(0);
  const [lastUpdate, setLastUpdate] = useState(Date.now());
  const ws = useRef(null);

  useEffect(() => {
    const url = getBackendUrl();
    setBackendUrl(url);
    setApiUrl(`${url}/api`);
    setWsBaseUrl(getWsBaseUrl());
  }, []);

  // Debug logging
  useEffect(() => {
    console.log("App initialized with:", {
      backendUrl,
      apiUrl,
      wsBaseUrl,
    });
  }, [backendUrl, apiUrl, wsBaseUrl]);

  useEffect(() => {
    if (sessionId) {
      console.log("Session ID changed, connecting WebSocket:", sessionId);
      connectWebSocket();
    }
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [sessionId]);

  const connectWebSocket = () => {
    if (ws.current) {
      ws.current.close();
    }

    const wsUrl = `${wsBaseUrl}/api/ws/${sessionId}?player_id=${playerId}`;
    console.log("Connecting to WebSocket:", wsUrl);

    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log("WebSocket connected successfully");
      setIsConnected(true);
      setError("");
      setWsRetryCount(0);

      // Send player identification
      if (playerId) {
        ws.current.send(
          JSON.stringify({
            type: "identify",
            player_id: playerId,
          })
        );
      }
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("Received WebSocket message:", data);
        if (data.type === "game_state") {
          setGameState(data);
          setLastUpdate(Date.now());
        } else if (data.type === "ping") {
          // Send pong back to keep connection alive
          if (ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({ type: "pong" }));
          }
        }
      } catch (e) {
        console.error("Error parsing WebSocket message:", e);
      }
    };

    ws.current.onclose = (event) => {
      console.log("WebSocket closed:", event.code, event.reason);
      setIsConnected(false);

      // Implement exponential backoff for reconnection
      if (event.code !== 1000 && sessionId && wsRetryCount < 5) {
        const delay = Math.min(1000 * Math.pow(2, wsRetryCount), 10000);
        console.log(
          `Attempting to reconnect in ${delay}ms (attempt ${wsRetryCount + 1})`
        );
        setTimeout(() => {
          setWsRetryCount((prev) => prev + 1);
          connectWebSocket();
        }, delay);
      } else if (wsRetryCount >= 5) {
        setError(
          "Failed to connect after multiple attempts. Using offline mode."
        );
        // Force fallback mode
        fetchGameState();
      }
    };

    ws.current.onerror = (error) => {
      console.error("WebSocket error:", error);
      setError("Connection error. Using offline mode...");
      setIsConnected(false);
    };
  };

  // Fallback method to get game state if WebSocket fails
  const fetchGameState = async () => {
    if (!sessionId) return;

    try {
      console.log("Fetching game state via API...");
      const response = await axios.get(`${apiUrl}/session/${sessionId}`);
      console.log("Fetched game state via API:", response.data);

      // Convert API response to match WebSocket format
      const gameStateData = {
        type: "game_state",
        session: response.data,
        player_id: playerId,
      };

      // Add role info for current player
      if (response.data.phase !== "lobby" && response.data.players) {
        const currentPlayer = response.data.players.find(
          (p) => p.id === playerId
        );
        if (currentPlayer && currentPlayer.role) {
          gameStateData.role_info = getRoleInfoFromSession(
            currentPlayer.role,
            response.data.players
          );
        }
      }

      // Add current mission details
      if (response.data.current_mission < response.data.missions.length) {
        gameStateData.current_mission_details =
          response.data.missions[response.data.current_mission];
      }

      setGameState(gameStateData);
      setLastUpdate(Date.now());
      setError("");
    } catch (error) {
      console.error("Failed to fetch game state:", error);
      setError(
        "Failed to fetch game state: " +
          (error.response?.data?.detail || error.message)
      );
    }
  };

  // Helper function to get role info from session data
  const getRoleInfoFromSession = (playerRole, allPlayers) => {
    const info = {
      role: playerRole,
      team: ["merlin", "percival", "loyal_servant"].includes(playerRole)
        ? "good"
        : "evil",
      description: "",
      sees: [],
    };

    // Add role-specific information (simplified version)
    switch (playerRole) {
      case "merlin":
        info.description = "You can see all evil players except Mordred";
        info.sees = allPlayers
          .filter((p) =>
            ["morgana", "assassin", "oberon", "minion"].includes(p.role)
          )
          .map((p) => ({ id: p.id, name: p.name, role: "evil" }));
        break;
      case "percival":
        info.description =
          "You can see Merlin and Morgana, but don't know which is which";
        info.sees = allPlayers
          .filter((p) => ["merlin", "morgana"].includes(p.role))
          .map((p) => ({ id: p.id, name: p.name, role: "merlin_or_morgana" }));
        break;
      case "morgana":
        info.description =
          "You are evil and can see other evil players (except Oberon)";
        info.sees = allPlayers
          .filter((p) => ["assassin", "mordred", "minion"].includes(p.role))
          .map((p) => ({ id: p.id, name: p.name, role: "evil" }));
        break;
      case "assassin":
        info.description =
          "You are evil and can see other evil players (except Oberon). You can assassinate Merlin if good wins";
        info.sees = allPlayers
          .filter((p) => ["morgana", "mordred", "minion"].includes(p.role))
          .map((p) => ({ id: p.id, name: p.name, role: "evil" }));
        break;
      case "mordred":
        info.description =
          "You are evil and can see other evil players (except Oberon). You are hidden from Merlin";
        info.sees = allPlayers
          .filter((p) => ["morgana", "assassin", "minion"].includes(p.role))
          .map((p) => ({ id: p.id, name: p.name, role: "evil" }));
        break;
      case "minion":
        info.description =
          "You are evil and can see other evil players (except Oberon)";
        info.sees = allPlayers
          .filter((p) => ["morgana", "assassin", "mordred"].includes(p.role))
          .map((p) => ({ id: p.id, name: p.name, role: "evil" }));
        break;
      case "oberon":
        info.description =
          "You are evil but hidden from other evil players and Merlin";
        break;
      default:
        info.description =
          "You are a loyal servant of Arthur. Trust in Merlin's guidance";
    }

    return info;
  };

  // Poll for game state if WebSocket is not connected
  useEffect(() => {
    if (sessionId && !isConnected) {
      // Start immediate polling when WebSocket fails
      fetchGameState();
      const interval = setInterval(fetchGameState, 2000); // Poll every 2 seconds
      return () => clearInterval(interval);
    }
  }, [sessionId, isConnected, playerId]);

  const createSession = async () => {
    try {
      setError("");
      console.log("Creating session...");
      const response = await axios.post(`${apiUrl}/create-session`, {
        name: sessionName,
        player_name: playerName,
      });
      console.log("Session created:", response.data);
      setSessionId(response.data.session_id);
      setPlayerId(response.data.player_id);
      setPlayerToken(response.data.player_token);

      // Fetch initial game state if WebSocket doesn't work
      setTimeout(fetchGameState, 1000);
    } catch (error) {
      console.error("Failed to create session:", error);
      setError(
        "Failed to create session: " +
          (error.response?.data?.detail || error.message)
      );
    }
  };

  const joinSession = async () => {
    try {
      setError("");
      console.log("Joining session...");
      const response = await axios.post(`${apiUrl}/join-session`, {
        session_id: sessionIdInput,
        player_name: playerName,
        as_spectator: joinAsSpectator,
      });
      console.log("Joined session:", response.data);
      setSessionId(sessionIdInput);
      setPlayerId(response.data.player_id);
      setPlayerToken(response.data.player_token);

      // Fetch initial game state if WebSocket doesn't work
      setTimeout(fetchGameState, 1000);
    } catch (error) {
      console.error("Failed to join session:", error);
      setError(
        "Failed to join session: " +
          (error.response?.data?.detail || error.message)
      );
    }
  };

  const startGame = async () => {
    try {
      await axios.post(`${apiUrl}/start-game`, {
        session_id: sessionId,
      });
      setError("");
      // Fetch updated game state
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError(
        "Failed to start game: " +
          (error.response?.data?.detail || error.message)
      );
    }
  };

  const startTestGame = async () => {
    try {
      await axios.post(`${apiUrl}/start-test-game`, {
        session_id: sessionId,
      });
      setError("");
      // Fetch updated game state
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError(
        "Failed to start test game: " +
          (error.response?.data?.detail || error.message)
      );
    }
  };

  const selectTeam = async () => {
    try {
      await axios.post(`${apiUrl}/select-team`, {
        session_id: sessionId,
        player_id: playerId,
        player_token: playerToken,
        team_members: selectedTeam,
      });
      setSelectedTeam([]);
      setError("");
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError("Failed to select team");
    }
  };

  const voteTeam = async (vote) => {
    try {
      await axios.post(`${apiUrl}/vote-team`, {
        session_id: sessionId,
        player_id: playerId,
        player_token: playerToken,
        vote: vote,
      });
      setError("");
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError("Failed to vote");
    }
  };

  const voteMission = async (vote) => {
    try {
      await axios.post(`${apiUrl}/vote-mission`, {
        session_id: sessionId,
        player_id: playerId,
        player_token: playerToken,
        vote: vote,
      });
      setError("");
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError("Failed to vote on mission");
    }
  };

  const useLadyOfLake = async () => {
    try {
      const response = await axios.post(`${apiUrl}/lady-of-lake`, {
        session_id: sessionId,
        player_id: playerId,
        player_token: playerToken,
        target_player_id: ladyTarget,
      });

      setLadyResult(response.data);
      setShowLadyResult(true);
      setLadyTarget(null);

      // Auto-hide result after 10 seconds
      setTimeout(() => {
        setShowLadyResult(false);
      }, 10000);
    } catch (error) {
      setError(
        error.response?.data?.detail || "Failed to use Lady of the Lake"
      );
    }
  };

  const assassinate = async () => {
    try {
      await axios.post(`${apiUrl}/assassinate`, {
        session_id: sessionId,
        player_id: playerId,
        player_token: playerToken,
        target_player_id: assassinTarget,
      });
      setAssassinTarget("");
      setError("");
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError("Failed to assassinate");
    }
  };

  const toggleLadyOfLake = async (enabled) => {
    try {
      await axios.post(`${apiUrl}/toggle-lady-of-lake`, {
        session_id: sessionId,
        enabled: enabled,
      });
      setError("");
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError(
        "Failed to toggle Lady of the Lake: " +
          (error.response?.data?.detail || error.message)
      );
    }
  };

  const restartGame = async () => {
    try {
      await axios.post(`${apiUrl}/restart-game`, {
        session_id: sessionId,
      });
      setError("");
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError(
        "Failed to restart game: " +
          (error.response?.data?.detail || error.message)
      );
    }
  };

  const endGame = async () => {
    try {
      await axios.post(`${apiUrl}/end-game`, {
        session_id: sessionId,
      });
      setShowEndGameConfirm(false);
    } catch (error) {
      setError(error.response?.data?.detail || "Failed to end game");
    }
  };

  const confirmEndGame = () => {
    setShowEndGameConfirm(true);
  };

  const toggleTeamMember = (playerIdToToggle) => {
    const currentMission = gameState?.current_mission_details;
    if (!currentMission) return;

    if (selectedTeam.includes(playerIdToToggle)) {
      setSelectedTeam(selectedTeam.filter((id) => id !== playerIdToToggle));
    } else if (selectedTeam.length < currentMission.team_size) {
      setSelectedTeam([...selectedTeam, playerIdToToggle]);
    }
  };

  const getCurrentPlayer = () => {
    return gameState?.session?.players?.find((p) => p.id === playerId);
  };

  const getCurrentLeader = () => {
    return gameState?.session?.players?.find((p) => p.is_leader);
  };

  const isCurrentPlayerLeader = () => {
    return getCurrentPlayer()?.is_leader;
  };

  const hasPlayerVoted = (playerId, votes) => {
    return votes && votes.hasOwnProperty(playerId);
  };

  const renderLobby = () => {
    const players = gameState?.session?.players || [];
    const activePlayers = players.filter((p) => !p.is_spectator);
    const spectators = players.filter((p) => p.is_spectator);
    const canStart = activePlayers.length >= 5;
    const currentPlayer = getCurrentPlayer();

    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 p-4">
        <div className="max-w-6xl mx-auto px-4">
          <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-8">
            <div className="text-center mb-6 sm:mb-8">
              <h1 className="text-xl sm:text-2xl md:text-4xl font-bold text-gray-800 mb-2">
                🏰 {gameState.session.name}
              </h1>
              <p className="text-xs sm:text-sm md:text-base text-gray-600">
                Waiting for players to join...
              </p>
              <div className="mt-2 flex flex-wrap justify-center items-center gap-2 text-xs sm:text-sm">
                <button
                  onClick={() =>
                    navigator.clipboard.writeText(gameState.session.id)
                  }
                  className="bg-blue-100 hover:bg-blue-200 text-blue-800 px-2 py-1 rounded transition-colors"
                  title="Tap to copy full session ID"
                >
                  Session ID: {gameState.session.id.slice(0, 8)}... 📋
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
              <div className="bg-gray-50 rounded-lg p-4 sm:p-6">
                <h3 className="text-base sm:text-lg md:text-xl font-bold mb-4 text-gray-700">
                  Active Players ({activePlayers.length}/10)
                </h3>
                <div className="space-y-2">
                  {activePlayers.map((player, index) => (
                    <div
                      key={player.id}
                      className={`flex items-center justify-between p-2 sm:p-3 rounded-lg text-xs sm:text-sm ${
                        player.id === playerId ? "bg-blue-200" : "bg-white"
                      }`}
                    >
                      <span className="font-medium truncate flex-1">
                        {player.name}
                      </span>
                      <div className="flex items-center space-x-2 flex-shrink-0">
                        {player.is_connected ? (
                          <span className="text-green-600 text-xs sm:text-sm">
                            🟢 Online
                          </span>
                        ) : (
                          <span className="text-red-600 text-xs sm:text-sm">
                            🔴 Offline
                          </span>
                        )}
                        {player.is_bot && (
                          <span className="text-purple-600 text-xs sm:text-sm">
                            🤖 Bot
                          </span>
                        )}
                        {player.id === playerId && (
                          <span className="bg-blue-500 text-white px-2 py-1 rounded text-xs">
                            You
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {spectators.length > 0 && (
                  <div className="mt-4">
                    <h4 className="text-xs font-semibold text-gray-600 mb-2">
                      Spectators ({spectators.length})
                    </h4>
                    <div className="space-y-1">
                      {spectators.map((player) => (
                        <div
                          key={player.id}
                          className={`flex items-center justify-between p-2 rounded-lg text-xs ${
                            player.id === playerId
                              ? "bg-purple-200"
                              : "bg-gray-100"
                          }`}
                        >
                          <span className="font-medium truncate flex-1">
                            👁️ {player.name}
                          </span>
                          <div className="flex items-center space-x-2 flex-shrink-0">
                            {player.is_connected ? (
                              <span className="text-green-600 text-xs">🟢</span>
                            ) : (
                              <span className="text-red-600 text-xs">🔴</span>
                            )}
                            {player.id === playerId && (
                              <span className="bg-purple-500 text-white px-2 py-1 rounded text-xs">
                                You
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-6">
                <div className="bg-gray-50 rounded-lg p-4 sm:p-6">
                  <h3 className="text-base sm:text-lg md:text-xl font-bold mb-4 text-gray-700">
                    Game Settings
                  </h3>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-semibold">Lady of the Lake</h4>
                        <p className="text-sm text-gray-600">
                          Reveal player allegiances (7+ players)
                        </p>
                      </div>
                      <button
                        onClick={() =>
                          toggleLadyOfLake(
                            !gameState.session.lady_of_the_lake_enabled
                          )
                        }
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                          gameState.session.lady_of_the_lake_enabled
                            ? "bg-yellow-500 hover:bg-yellow-600 text-white"
                            : "bg-gray-300 hover:bg-gray-400 text-gray-700"
                        }`}
                      >
                        {gameState.session.lady_of_the_lake_enabled
                          ? "Enabled"
                          : "Disabled"}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 rounded-lg p-4 sm:p-6">
                  <h3 className="text-base sm:text-lg md:text-xl font-bold mb-4 text-gray-700">
                    Game Rules
                  </h3>
                  <div className="space-y-3 text-xs sm:text-sm">
                    <div>
                      <h4 className="font-semibold">📝 Mission Overview:</h4>
                      <p>Complete 3 out of 5 missions to win as Good</p>
                    </div>
                    <div>
                      <h4 className="font-semibold">👥 Team Formation:</h4>
                      <p>Leader proposes teams, everyone votes</p>
                    </div>
                    <div>
                      <h4 className="font-semibold">⚔️ Mission Execution:</h4>
                      <p>Team members secretly vote Success/Fail</p>
                    </div>
                    <div>
                      <h4 className="font-semibold">🗡️ Assassination:</h4>
                      <p>
                        If Good wins, Assassin can kill Merlin for Evil victory
                      </p>
                    </div>
                    {gameState.session.lady_of_the_lake_enabled &&
                      activePlayers.length >= 7 && (
                        <div>
                          <h4 className="font-semibold">
                            🌟 Lady of the Lake:
                          </h4>
                          <p>
                            Reveal a player's allegiance after missions 2 & 3
                          </p>
                        </div>
                      )}
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-6 sm:mt-8 text-center">
              {canStart && !currentPlayer?.is_spectator ? (
                <div className="space-y-4">
                  <button
                    onClick={startGame}
                    className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 sm:py-3 px-4 sm:px-8 rounded-lg text-base sm:text-lg transition-colors mr-0 sm:mr-4 mb-2 sm:mb-0 w-full sm:w-auto"
                  >
                    🚀 Start Game
                  </button>
                  <div>
                    <button
                      onClick={startTestGame}
                      className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 sm:px-6 rounded-lg transition-colors w-full sm:w-auto"
                    >
                      🧪 Start Test Game (adds bots)
                    </button>
                    <p className="text-xs text-gray-500 mt-1">
                      Test mode adds bot players for testing
                    </p>
                  </div>
                </div>
              ) : currentPlayer?.is_spectator ? (
                <div className="text-gray-600">
                  <p>You are spectating this game</p>
                  <p>Waiting for other players to start...</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="text-gray-600">
                    <p>Need at least 5 players to start</p>
                    <p>({5 - activePlayers.length} more needed)</p>
                  </div>
                  <button
                    onClick={startTestGame}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 sm:px-6 rounded-lg transition-colors w-full sm:w-auto"
                  >
                    🧪 Start Test Game (adds bots)
                  </button>
                  <p className="text-xs text-gray-500">
                    Test mode adds bot players so you can try the game
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderGame = () => {
    const session = gameState?.session;
    const currentMission = gameState?.current_mission_details;
    const roleInfo = gameState?.role_info;
    const currentPlayer = getCurrentPlayer();
    const currentLeader = getCurrentLeader();

    if (!session || !currentPlayer) return null;

    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 p-4">
        <div className="max-w-6xl mx-auto px-4">
          {/* Header */}
          <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6 mb-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex-1 min-w-0">
                <h1 className="text-lg sm:text-xl md:text-2xl font-bold text-gray-800 truncate">
                  🏰 {session.name}
                </h1>
                <p className="text-xs sm:text-sm md:text-base text-gray-600">
                  Phase: {session.phase.replace("_", " ").toUpperCase()}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs sm:text-sm">
                  <button
                    onClick={() => navigator.clipboard.writeText(session.id)}
                    className="bg-blue-100 hover:bg-blue-200 text-blue-800 px-2 py-1 rounded transition-colors"
                    title="Tap to copy full session ID"
                  >
                    ID: {session.id.slice(0, 8)}... 📋
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3 sm:gap-4 text-xs sm:text-sm">
                <div className="flex items-center space-x-2">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      isConnected ? "bg-green-500" : "bg-yellow-500"
                    }`}
                  ></div>
                  <span className="text-gray-600">
                    {isConnected ? "Real-time" : "Offline Mode"}
                  </span>
                  {!isConnected && (
                    <button
                      onClick={fetchGameState}
                      className="text-xs bg-blue-500 hover:bg-blue-600 text-white px-2 py-1 rounded transition-colors"
                    >
                      Refresh
                    </button>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div>
                    <p className="text-xs text-gray-600">Good Wins</p>
                    <p className="text-lg font-bold text-green-600">
                      {session.good_wins}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-600">Evil Wins</p>
                    <p className="text-lg font-bold text-red-600">
                      {session.evil_wins}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-600">Vote Track</p>
                    <p className="text-lg font-bold text-yellow-600">
                      {session.vote_track}/5
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
            {/* Main Panel - Game Info */}
            <div className="lg:col-span-2 space-y-4 sm:space-y-6 order-2 lg:order-1">
              {/* On mobile: show current mission ACTION first (vote/select) before missions grid */}
              <div className="lg:hidden">
                {currentMission && (session.phase === "mission_voting" || session.phase === "mission_execution" || session.phase === "mission_team_selection") && (
                  <div className="bg-yellow-50 border-2 border-yellow-400 rounded-xl p-4 mb-4">
                    <p className="text-sm font-bold text-yellow-800 text-center">
                      {session.phase === "mission_team_selection" && isCurrentPlayerLeader() && `Select ${currentMission.team_size} players for the mission`}
                      {session.phase === "mission_team_selection" && !isCurrentPlayerLeader() && `Waiting for ${currentLeader?.name} to select team...`}
                      {session.phase === "mission_voting" && !hasPlayerVoted(playerId, currentMission.votes) && "Vote on the proposed team!"}
                      {session.phase === "mission_voting" && hasPlayerVoted(playerId, currentMission.votes) && "Waiting for other votes..."}
                      {session.phase === "mission_execution" && currentMission.team_members.includes(playerId) && !hasPlayerVoted(playerId, currentMission.mission_votes) && "You're on the mission! Vote now."}
                      {session.phase === "mission_execution" && (!currentMission.team_members.includes(playerId) || hasPlayerVoted(playerId, currentMission.mission_votes)) && "Mission in progress..."}
                    </p>
                  </div>
                )}
              </div>
              {/* Role Info */}
              {roleInfo && (
                <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                  <h2 className="text-base sm:text-lg md:text-xl font-bold mb-4 text-gray-800">
                    🎭 Your Role:{" "}
                    {roleInfo.role.replace("_", " ").toUpperCase()}
                  </h2>
                  <div
                    className={`p-4 rounded-lg ${
                      roleInfo.team === "good"
                        ? "bg-blue-50 border-l-4 border-blue-500"
                        : "bg-red-50 border-l-4 border-red-500"
                    }`}
                  >
                    <p className="font-medium mb-2 text-xs sm:text-sm">
                      Team:{" "}
                      <span
                        className={
                          roleInfo.team === "good"
                            ? "text-blue-600"
                            : "text-red-600"
                        }
                      >
                        {roleInfo.team.toUpperCase()}
                      </span>
                    </p>
                    <p className="text-xs sm:text-sm text-gray-700 mb-3">
                      {roleInfo.description}
                    </p>
                    {roleInfo.sees && roleInfo.sees.length > 0 && (
                      <div>
                        <p className="font-medium text-xs sm:text-sm mb-2">
                          You can see:
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {roleInfo.sees.map((seePlayer, index) => (
                            <span
                              key={index}
                              className="bg-gray-200 px-2 py-1 rounded text-xs"
                            >
                              {seePlayer.name} ({seePlayer.role})
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Lady of the Lake Knowledge */}
                  {gameState?.lady_of_lake_knowledge &&
                    gameState.lady_of_lake_knowledge.length > 0 && (
                      <div className="mt-4 p-4 bg-yellow-50 border-l-4 border-yellow-500 rounded-lg">
                        <h3 className="font-bold text-yellow-800 mb-2 text-xs sm:text-sm">
                          🌟 Lady of the Lake Knowledge:
                        </h3>
                        <div className="space-y-2">
                          {gameState.lady_of_lake_knowledge.map(
                            (knowledge, index) => (
                              <div
                                key={index}
                                className={`inline-block px-3 py-1 rounded-lg text-xs sm:text-sm font-medium mr-2 ${
                                  knowledge.allegiance === "good"
                                    ? "bg-blue-500 text-white"
                                    : "bg-red-500 text-white"
                                }`}
                              >
                                {knowledge.target_name}:{" "}
                                {knowledge.allegiance.toUpperCase()}
                              </div>
                            )
                          )}
                        </div>
                        <p className="text-xs text-yellow-700 mt-2">
                          This information persists throughout the game
                        </p>
                      </div>
                    )}
                </div>
              )}

              {/* Mission Info */}
              <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                <h2 className="text-lg sm:text-xl font-bold mb-4 text-gray-800">
                  📋 Missions
                </h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 mb-4 overflow-x-auto">
                  {session.missions.map((mission, index) => (
                    <div
                      key={index}
                      className={`p-2 sm:p-3 rounded-lg text-center border-2 text-xs sm:text-sm ${
                        index === session.current_mission
                          ? "bg-yellow-100 border-yellow-500"
                          : mission.result === "success"
                          ? "bg-green-100 border-green-500"
                          : mission.result === "fail"
                          ? "bg-red-100 border-red-500"
                          : "bg-gray-100 border-gray-300"
                      }`}
                    >
                      <div className="text-xs sm:text-base font-bold">
                        #{mission.number}
                      </div>
                      <div className="text-xs">{mission.team_size} players</div>
                      <div className="text-xs">
                        {mission.fails_required} fail
                        {mission.fails_required > 1 ? "s" : ""} needed
                      </div>
                      {mission.result !== "pending" && (
                        <div
                          className={`text-xs font-bold ${
                            mission.result === "success"
                              ? "text-green-600"
                              : "text-red-600"
                          }`}
                        >
                          {mission.result.toUpperCase()}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Current Mission Details */}
              {currentMission && (
                <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                  <h2 className="text-lg sm:text-xl font-bold mb-4 text-gray-800">
                    🎯 Mission {currentMission.number}
                  </h2>

                  {session.phase === "mission_team_selection" && (
                    <div>
                      <p className="mb-4">
                        <strong>Leader:</strong> {currentLeader?.name} must
                        select {currentMission.team_size} players
                      </p>

                      {isCurrentPlayerLeader() && (
                        <div className="space-y-4">
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                            {session.players
                              .filter((p) => !p.is_spectator)
                              .map((player) => (
                                <button
                                  key={player.id}
                                  onClick={() => toggleTeamMember(player.id)}
                                  className={`p-2 sm:p-3 rounded-lg border-2 transition-colors text-xs sm:text-sm ${
                                    selectedTeam.includes(player.id)
                                      ? "bg-blue-500 text-white border-blue-500"
                                      : "bg-white border-gray-300 hover:border-blue-300"
                                  }`}
                                >
                                  {player.name}
                                </button>
                              ))}
                          </div>

                          <div className="text-center">
                            <p className="mb-2">
                              Selected: {selectedTeam.length}/
                              {currentMission.team_size}
                            </p>
                            <button
                              onClick={selectTeam}
                              disabled={
                                selectedTeam.length !== currentMission.team_size
                              }
                              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-bold py-2 px-4 sm:px-6 rounded-lg transition-colors"
                            >
                              Propose Team
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {session.phase === "mission_voting" && (
                    <div>
                      <p className="mb-4">
                        <strong>Proposed Team:</strong>{" "}
                        {currentMission.team_members
                          .map(
                            (id) =>
                              session.players.find((p) => p.id === id)?.name
                          )
                          .join(", ")}
                      </p>

                      <div className="mb-4">
                        <h4 className="font-semibold mb-2">Votes:</h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                          {session.players
                            .filter((p) => !p.is_spectator)
                            .map((player) => (
                              <div
                                key={player.id}
                                className={`p-2 rounded border text-xs sm:text-sm ${
                                  hasPlayerVoted(
                                    player.id,
                                    currentMission.votes
                                  )
                                    ? "bg-blue-100 border-blue-300"
                                    : "bg-gray-100 border-gray-300"
                                }`}
                              >
                                <span className="font-medium">
                                  {player.name}
                                </span>
                                {hasPlayerVoted(
                                  player.id,
                                  currentMission.votes
                                ) && (
                                  <span className="ml-2 text-xs">✓ Voted</span>
                                )}
                              </div>
                            ))}
                        </div>
                      </div>

                      {!hasPlayerVoted(playerId, currentMission.votes) && (
                        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center">
                          <button
                            onClick={() => voteTeam(true)}
                            className="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-6 rounded-lg transition-colors text-base min-h-[48px]"
                          >
                            ✓ Approve
                          </button>
                          <button
                            onClick={() => voteTeam(false)}
                            className="bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-6 rounded-lg transition-colors text-base min-h-[48px]"
                          >
                            ✗ Reject
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {session.phase === "mission_execution" && (
                    <div>
                      <p className="mb-4">
                        <strong>Mission Team:</strong>{" "}
                        {currentMission.team_members
                          .map(
                            (id) =>
                              session.players.find((p) => p.id === id)?.name
                          )
                          .join(", ")}
                      </p>

                      {currentMission.team_members.includes(playerId) && (
                        <div>
                          <p className="mb-4 font-semibold">
                            You are on this mission! Choose your action:
                          </p>

                          {!hasPlayerVoted(
                            playerId,
                            currentMission.mission_votes
                          ) && (
                            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center">
                              <button
                                onClick={() => voteMission(true)}
                                className="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-6 rounded-lg transition-colors text-base min-h-[48px]"
                              >
                                ✓ Success
                              </button>
                              {roleInfo?.team === "evil" && (
                                <button
                                  onClick={() => voteMission(false)}
                                  className="bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-6 rounded-lg transition-colors text-base min-h-[48px]"
                                >
                                  ✗ Fail
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      <div className="mt-4">
                        <h4 className="font-semibold mb-2">Mission Votes:</h4>
                        {currentMission.mission_votes?.total_votes ? (
                          <div className="bg-gray-100 p-3 rounded-lg">
                            <p className="text-xs sm:text-sm text-gray-700">
                              {currentMission.mission_votes.total_votes} team
                              members have voted
                            </p>
                            {currentMission.result !== "pending" && (
                              <p className="text-xs sm:text-sm font-medium mt-1">
                                Result:{" "}
                                {currentMission.mission_votes.success_count}{" "}
                                success,{" "}
                                {currentMission.mission_votes.fail_count} fail
                                votes
                              </p>
                            )}
                          </div>
                        ) : (
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                            {currentMission.team_members.map((memberId) => {
                              const member = session.players.find(
                                (p) => p.id === memberId
                              );
                              return (
                                <div
                                  key={memberId}
                                  className={`p-2 rounded border text-xs sm:text-sm ${
                                    currentMission.mission_votes
                                      ?.player_voted && memberId === playerId
                                      ? "bg-blue-100 border-blue-300"
                                      : "bg-gray-100 border-gray-300"
                                  }`}
                                >
                                  <span className="font-medium">
                                    {member?.name}
                                  </span>
                                  {currentMission.mission_votes?.player_voted &&
                                    memberId === playerId && (
                                      <span className="ml-2 text-xs">
                                        ✓ Voted
                                      </span>
                                    )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Lady of the Lake */}
              {session.phase === "lady_of_the_lake" && (
                <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                  <h2 className="text-lg sm:text-xl font-bold mb-4 text-gray-800">
                    🌟 Lady of the Lake
                  </h2>

                  {currentPlayer.lady_of_the_lake && (
                    <div className="space-y-4">
                      <p className="font-semibold">
                        You have the Lady of the Lake! Choose a player to reveal
                        their allegiance:
                      </p>

                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {session.players
                          .filter((p) => p.id !== playerId && !p.is_spectator)
                          .map((player) => (
                            <button
                              key={player.id}
                              onClick={() => setLadyTarget(player.id)}
                              className={`p-2 sm:p-3 rounded-lg border-2 transition-colors text-xs sm:text-sm ${
                                ladyTarget === player.id
                                  ? "bg-yellow-500 text-white border-yellow-500"
                                  : "bg-white border-gray-300 hover:border-yellow-300"
                              }`}
                            >
                              {player.name}
                            </button>
                          ))}
                      </div>

                      {ladyTarget && (
                        <div className="text-center">
                          <button
                            onClick={useLadyOfLake}
                            className="bg-yellow-600 hover:bg-yellow-700 text-white font-bold py-2 px-4 sm:px-6 rounded-lg transition-colors"
                          >
                            Use Lady of the Lake
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {ladyResult && showLadyResult && (
                    <div className="mt-4 p-4 bg-gradient-to-r from-yellow-50 to-yellow-100 border-2 border-yellow-300 rounded-lg animate-pulse shadow-lg">
                      <div className="text-center">
                        <h4 className="text-base sm:text-lg font-bold text-yellow-800 mb-2">
                          🌟 Lady of the Lake Reveals:
                        </h4>
                        <div
                          className={`inline-block px-4 py-2 rounded-lg font-bold text-base sm:text-lg shadow-md ${
                            ladyResult.allegiance === "good"
                              ? "bg-blue-500 text-white border-2 border-blue-600"
                              : "bg-red-500 text-white border-2 border-red-600"
                          }`}
                        >
                          {ladyResult.target_name} is{" "}
                          {ladyResult.allegiance.toUpperCase()}
                        </div>
                        <p className="text-xs sm:text-sm text-yellow-700 mt-2 font-medium">
                          {ladyResult.allegiance === "good"
                            ? "✓ This player serves Arthur"
                            : "⚠️ This player serves Mordred"}
                        </p>
                        <p className="text-xs text-yellow-600 mt-1">
                          (This message will disappear in 10 seconds)
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Assassination Phase */}
              {session.phase === "assassination" && (
                <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                  <h2 className="text-lg sm:text-xl font-bold mb-4 text-gray-800">
                    🗡️ Assassination
                  </h2>

                  {roleInfo?.role === "assassin" && (
                    <div className="space-y-4">
                      <p className="font-semibold text-red-600">
                        Good has won the missions, but you can still win by
                        assassinating Merlin!
                      </p>

                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {session.players
                          .filter((p) => p.id !== playerId && !p.is_spectator)
                          .map((player) => (
                            <button
                              key={player.id}
                              onClick={() => setAssassinTarget(player.id)}
                              className={`p-2 sm:p-3 rounded-lg border-2 transition-colors text-xs sm:text-sm ${
                                assassinTarget === player.id
                                  ? "bg-red-500 text-white border-red-500"
                                  : "bg-white border-gray-300 hover:border-red-300"
                              }`}
                            >
                              {player.name}
                            </button>
                          ))}
                      </div>

                      {assassinTarget && (
                        <div className="text-center">
                          <button
                            onClick={assassinate}
                            className="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 sm:px-6 rounded-lg transition-colors"
                          >
                            Assassinate{" "}
                            {
                              session.players.find(
                                (p) => p.id === assassinTarget
                              )?.name
                            }
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {roleInfo?.role !== "assassin" && (
                    <p className="text-center text-xs sm:text-sm text-gray-600">
                      The Assassin is choosing their target...
                    </p>
                  )}
                </div>
              )}

              {/* Game End */}
              {session.phase === "game_end" && (
                <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                  <h2 className="text-lg sm:text-xl font-bold mb-4 text-gray-800">
                    🎉 Game Over!
                  </h2>

                  <div className="text-center">
                    <p className="text-lg sm:text-2xl font-bold mb-4">
                      {session.game_result === "good" ? (
                        <span className="text-blue-600">✓ GOOD WINS!</span>
                      ) : (
                        <span className="text-red-600">✗ EVIL WINS!</span>
                      )}
                    </p>

                    <div className="mt-6">
                      <h3 className="font-semibold mb-2 text-xs sm:text-sm">
                        Player Roles:
                      </h3>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {session.players
                          .filter((p) => !p.is_spectator)
                          .map((player) => (
                            <div
                              key={player.id}
                              className={`p-2 rounded border text-xs sm:text-sm ${
                                [
                                  "merlin",
                                  "percival",
                                  "loyal_servant",
                                ].includes(player.role)
                                  ? "bg-blue-100 border-blue-300"
                                  : "bg-red-100 border-red-300"
                              }`}
                            >
                              <span className="font-medium">{player.name}</span>
                              <span className="ml-2 text-xs">
                                ({player.role?.replace("_", " ") || "Unknown"})
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Side Panel - Players and Controls */}
            <div className="space-y-4 sm:space-y-6 order-3 lg:order-2">
              {/* Players */}
              <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                <h2 className="text-base sm:text-lg md:text-xl font-bold mb-4 text-gray-800">
                  👥 Players
                </h2>

                {/* Active Players */}
                <div className="space-y-2 mb-4">
                  <h3 className="text-xs sm:text-sm font-semibold text-gray-600 uppercase tracking-wide">
                    Active Players
                  </h3>
                  {session.players
                    .filter((p) => !p.is_spectator)
                    .map((player) => (
                      <div
                        key={player.id}
                        className={`p-2 sm:p-3 rounded-lg border-2 text-xs sm:text-sm ${
                          player.id === playerId
                            ? "bg-blue-100 border-blue-300"
                            : "bg-gray-50 border-gray-200"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium truncate flex-1">
                            {player.name}
                          </span>
                          <div className="flex items-center space-x-1 flex-shrink-0">
                            {player.is_leader && (
                              <span
                                className="text-yellow-600 text-xs sm:text-sm"
                                title="Leader"
                              >
                                👑
                              </span>
                            )}
                            {player.lady_of_the_lake && (
                              <span
                                className="text-yellow-600 text-xs sm:text-sm"
                                title="Lady of the Lake"
                              >
                                🌟
                              </span>
                            )}
                            {player.is_bot && (
                              <span
                                className="text-purple-600 text-xs sm:text-sm"
                                title="Bot"
                              >
                                🤖
                              </span>
                            )}
                            {player.is_connected ? (
                              <span
                                className="text-green-600 text-xs sm:text-sm"
                                title="Online"
                              >
                                🟢
                              </span>
                            ) : (
                              <span
                                className="text-red-600 text-xs sm:text-sm"
                                title="Offline"
                              >
                                🔴
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                </div>

                {/* Spectators */}
                {session.players.filter((p) => p.is_spectator).length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-xs sm:text-sm font-semibold text-gray-600 uppercase tracking-wide">
                      Spectators
                    </h3>
                    {session.players
                      .filter((p) => p.is_spectator)
                      .map((player) => (
                        <div
                          key={player.id}
                          className={`p-2 rounded-lg border text-xs sm:text-sm ${
                            player.id === playerId
                              ? "bg-purple-100 border-purple-300"
                              : "bg-gray-50 border-gray-200"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium truncate flex-1">
                              👁️ {player.name}
                            </span>
                            <div className="flex items-center space-x-1 flex-shrink-0">
                              {player.is_connected ? (
                                <span
                                  className="text-green-600 text-xs sm:text-sm"
                                  title="Online"
                                >
                                  🟢
                                </span>
                              ) : (
                                <span
                                  className="text-red-600 text-xs sm:text-sm"
                                  title="Offline"
                                >
                                  🔴
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </div>

              {/* End Game Confirmation Modal */}
              {showEndGameConfirm && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                  <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6 max-w-md w-full">
                    <h3 className="text-lg sm:text-xl font-bold text-gray-800 mb-4">
                      🏁 End Game Confirmation
                    </h3>
                    <p className="text-xs sm:text-sm text-gray-600 mb-6">
                      Are you sure you want to end the game now? This will
                      immediately reveal all player roles and end the current
                      game.
                    </p>
                    <div className="flex gap-3">
                      <button
                        onClick={() => setShowEndGameConfirm(false)}
                        className="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-700 font-bold py-2 px-4 rounded-lg transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={endGame}
                        className="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded-lg transition-colors"
                      >
                        Yes, End Game
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Game Controls */}
              <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                <h2 className="text-base sm:text-lg md:text-xl font-bold mb-4 text-gray-800">
                  🎮 Game Controls
                </h2>

                <div className="space-y-3">
                  <button
                    onClick={() => setShowVoteHistory(!showVoteHistory)}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg transition-colors"
                  >
                    {showVoteHistory ? "Hide" : "Show"} Vote History
                  </button>

                  <button
                    onClick={() => setShowGameLog(!showGameLog)}
                    className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-lg transition-colors"
                  >
                    {showGameLog ? "Hide" : "Show"} Game Log
                  </button>

                  {session.phase !== "game_end" && (
                    <button
                      onClick={confirmEndGame}
                      className="w-full bg-orange-600 hover:bg-orange-700 text-white font-bold py-2 px-4 rounded-lg transition-colors"
                    >
                      🏁 End Game & Reveal Roles
                    </button>
                  )}

                  {session.phase === "game_end" && (
                    <button
                      onClick={restartGame}
                      className="w-full bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded-lg transition-colors"
                    >
                      🔄 Restart Game
                    </button>
                  )}
                </div>
              </div>

              {/* Vote History */}
              {showVoteHistory &&
                session.vote_history &&
                session.vote_history.length > 0 && (
                  <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                    <h2 className="text-lg sm:text-xl font-bold mb-4 text-gray-800">
                      📊 Vote History
                    </h2>
                    <div className="space-y-3 max-h-64 overflow-y-auto">
                      {session.vote_history.map((vote, index) => (
                        <div key={index} className="p-3 bg-gray-50 rounded-lg">
                          <div className="font-semibold text-xs sm:text-sm">
                            Mission {vote.mission} Team Vote - {vote.result}
                          </div>
                          <div className="text-xs text-gray-600 mt-1">
                            {vote.approve_count}/{vote.total_votes} approved
                          </div>
                          <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
                            {Object.entries(vote.votes).map(
                              ([playerName, playerVote]) => (
                                <div
                                  key={playerName}
                                  className="flex justify-between"
                                >
                                  <span>{playerName}:</span>
                                  <span
                                    className={
                                      playerVote
                                        ? "text-green-600"
                                        : "text-red-600"
                                    }
                                  >
                                    {playerVote ? "✓" : "✗"}
                                  </span>
                                </div>
                              )
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {/* Game Log */}
              {showGameLog &&
                session.game_log &&
                session.game_log.length > 0 && (
                  <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                    <h2 className="text-lg sm:text-xl font-bold mb-4 text-gray-800">
                      📝 Game Log
                    </h2>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {session.game_log.map((log, index) => (
                        <div
                          key={index}
                          className="p-2 bg-gray-50 rounded text-xs sm:text-sm"
                        >
                          {log}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderMainMenu = () => (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-2xl p-4 sm:p-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl sm:text-4xl font-bold text-gray-800 mb-2">
            🏰 Avalon
          </h1>
          <p className="text-xs sm:text-sm text-gray-600">
            The Resistance Board Game
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 sm:p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg text-xs sm:text-sm">
            {error}
          </div>
        )}

        {!isConnected && gameState && (
          <div className="mb-4 p-2 sm:p-3 bg-yellow-100 border border-yellow-400 text-yellow-700 rounded-lg text-xs sm:text-sm">
            ⚠️ Using offline mode - click refresh button or wait for auto-update
            (last update: {new Date(lastUpdate).toLocaleTimeString()})
          </div>
        )}

        <div className="space-y-4 sm:space-y-6">
          <div>
            <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-2">
              Your Name
            </label>
            <input
              type="text"
              value={playerName}
              onChange={(e) => setPlayerName(e.target.value)}
              className="w-full px-2 sm:px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-xs sm:text-sm"
              placeholder="Enter your name..."
            />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-2">
                Create New Session
              </label>
              <input
                type="text"
                value={sessionName}
                onChange={(e) => setSessionName(e.target.value)}
                className="w-full px-2 sm:px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 mb-2 text-xs sm:text-sm"
                placeholder="Session name..."
              />
              <button
                onClick={createSession}
                disabled={!playerName || !sessionName}
                className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded-lg transition-colors text-xs sm:text-sm"
              >
                Create Session
              </button>
            </div>

            <div className="text-center text-gray-500 text-xs sm:text-sm">
              <span>or</span>
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-2">
                Join Existing Session
              </label>
              <input
                type="text"
                value={sessionIdInput}
                onChange={(e) => setSessionIdInput(e.target.value)}
                className="w-full px-2 sm:px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 mb-2 text-xs sm:text-sm"
                placeholder="Session ID..."
              />
              <div className="mb-2">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={joinAsSpectator}
                    onChange={(e) => setJoinAsSpectator(e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-xs sm:text-sm text-gray-700">
                    Join as spectator (watch only)
                  </span>
                </label>
              </div>
              <button
                onClick={joinSession}
                disabled={!playerName || !sessionIdInput}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded-lg transition-colors text-xs sm:text-sm"
              >
                {joinAsSpectator ? "Join as Spectator" : "Join Session"}
              </button>
            </div>
          </div>
        </div>

        <div className="mt-6 sm:mt-8 text-center text-xs sm:text-sm text-gray-500">
          <p>🎭 Social deduction game for 5-10 players</p>
          <p>Complete missions as Good or sabotage as Evil</p>
        </div>
      </div>
    </div>
  );

  if (!gameState) {
    return renderMainMenu();
  }

  if (gameState.session?.phase === "lobby") {
    return renderLobby();
  }

  return renderGame();
}

export default App;
