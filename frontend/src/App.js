import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import axios from 'axios';

// Environment variable access compatible with React 19 and craco
const getBackendUrl = () => {
  // Try different methods to access environment variables
  if (typeof window !== 'undefined' && window.process && window.process.env) {
    return window.process.env.REACT_APP_BACKEND_URL;
  }
  if (typeof process !== 'undefined' && process.env) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  // Fallback - this will be replaced during build
  return 'https://6dea0238-f0e0-412c-a0be-b01fdaec96fe.preview.emergentagent.com';
};

const BACKEND_URL = getBackendUrl();
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

const ROLE_DESCRIPTIONS = {
  merlin: "You can see all evil players except Mordred. Guide the good team to victory, but stay hidden from the Assassin.",
  percival: "You can see Merlin and Morgana, but don't know which is which. Protect Merlin while following their guidance.",
  loyal_servant: "You are a loyal servant of Arthur. Trust in Merlin's guidance and help complete missions.",
  morgana: "You appear as Merlin to Percival. Use this to confuse the good team while working with evil.",
  assassin: "You can see other evil players. If good wins, you can assassinate Merlin to win the game for evil.",
  mordred: "You are hidden from Merlin. Use this advantage to infiltrate missions and lead evil to victory.",
  oberon: "You are hidden from everyone. Work alone to sabotage missions without being detected.",
  minion: "You can see other evil players. Work together to sabotage missions and achieve evil victory."
};

const MISSION_CONFIGS = {
  5: [[2, 1], [3, 1], [2, 1], [3, 1], [3, 1]],
  6: [[2, 1], [3, 1], [4, 1], [3, 1], [4, 1]],
  7: [[2, 1], [3, 1], [3, 1], [4, 2], [4, 1]],
  8: [[3, 1], [4, 1], [4, 1], [5, 2], [5, 1]],
  9: [[3, 1], [4, 1], [4, 1], [5, 2], [5, 1]],
  10: [[3, 1], [4, 1], [4, 1], [5, 2], [5, 1]]
};

function App() {
  const [gameState, setGameState] = useState(null);
  const [playerId, setPlayerId] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [playerName, setPlayerName] = useState('');
  const [sessionName, setSessionName] = useState('');
  const [sessionIdInput, setSessionIdInput] = useState('');
  const [selectedTeam, setSelectedTeam] = useState([]);
  const [ladyTarget, setLadyTarget] = useState('');
  const [assassinTarget, setAssassinTarget] = useState('');
  const [ladyResult, setLadyResult] = useState(null);
  const [showVoteHistory, setShowVoteHistory] = useState(false);
  const [showGameLog, setShowGameLog] = useState(false);
  const [error, setError] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [wsRetryCount, setWsRetryCount] = useState(0);
  const [lastUpdate, setLastUpdate] = useState(Date.now());
  const ws = useRef(null);

  // Debug logging
  useEffect(() => {
    console.log('App initialized with:', {
      BACKEND_URL,
      API,
      WS_URL
    });
  }, []);

  useEffect(() => {
    if (sessionId) {
      console.log('Session ID changed, connecting WebSocket:', sessionId);
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
    
    const wsUrl = `${WS_URL}/api/ws/${sessionId}?player_id=${playerId}`;
    console.log('Connecting to WebSocket:', wsUrl);
    
    ws.current = new WebSocket(wsUrl);
    
    ws.current.onopen = () => {
      console.log('WebSocket connected successfully');
      setIsConnected(true);
      setError('');
      setWsRetryCount(0);
      
      // Send player identification
      if (playerId) {
        ws.current.send(JSON.stringify({
          type: 'identify',
          player_id: playerId
        }));
      }
    };
    
    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received WebSocket message:', data);
        if (data.type === 'game_state') {
          setGameState(data);
          setLastUpdate(Date.now());
        } else if (data.type === 'ping') {
          // Send pong back to keep connection alive
          if (ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify({type: 'pong'}));
          }
        }
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    };
    
    ws.current.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
      setIsConnected(false);
      
      // Implement exponential backoff for reconnection
      if (event.code !== 1000 && sessionId && wsRetryCount < 5) {
        const delay = Math.min(1000 * Math.pow(2, wsRetryCount), 10000);
        console.log(`Attempting to reconnect in ${delay}ms (attempt ${wsRetryCount + 1})`);
        setTimeout(() => {
          setWsRetryCount(prev => prev + 1);
          connectWebSocket();
        }, delay);
      } else if (wsRetryCount >= 5) {
        setError('Failed to connect after multiple attempts. Using offline mode.');
        // Force fallback mode
        fetchGameState();
      }
    };
    
    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setError('Connection error. Using offline mode...');
      setIsConnected(false);
    };
  };

  // Fallback method to get game state if WebSocket fails
  const fetchGameState = async () => {
    if (!sessionId) return;
    
    try {
      console.log('Fetching game state via API...');
      const response = await axios.get(`${API}/session/${sessionId}`);
      console.log('Fetched game state via API:', response.data);
      
      // Convert API response to match WebSocket format
      const gameStateData = {
        type: 'game_state',
        session: response.data,
        player_id: playerId
      };
      
      // Add role info for current player
      if (response.data.phase !== 'lobby' && response.data.players) {
        const currentPlayer = response.data.players.find(p => p.id === playerId);
        if (currentPlayer && currentPlayer.role) {
          gameStateData.role_info = getRoleInfoFromSession(currentPlayer.role, response.data.players);
        }
      }
      
      // Add current mission details
      if (response.data.current_mission < response.data.missions.length) {
        gameStateData.current_mission_details = response.data.missions[response.data.current_mission];
      }
      
      setGameState(gameStateData);
      setLastUpdate(Date.now());
      setError('');
    } catch (error) {
      console.error('Failed to fetch game state:', error);
      setError('Failed to fetch game state: ' + (error.response?.data?.detail || error.message));
    }
  };

  // Helper function to get role info from session data
  const getRoleInfoFromSession = (playerRole, allPlayers) => {
    const info = {
      role: playerRole,
      team: ['merlin', 'percival', 'loyal_servant'].includes(playerRole) ? 'good' : 'evil',
      description: '',
      sees: []
    };
    
    // Add role-specific information (simplified version)
    switch (playerRole) {
      case 'merlin':
        info.description = 'You can see all evil players except Mordred';
        info.sees = allPlayers.filter(p => ['morgana', 'assassin', 'oberon', 'minion'].includes(p.role))
          .map(p => ({id: p.id, name: p.name, role: 'evil'}));
        break;
      case 'percival':
        info.description = 'You can see Merlin and Morgana, but don\'t know which is which';
        info.sees = allPlayers.filter(p => ['merlin', 'morgana'].includes(p.role))
          .map(p => ({id: p.id, name: p.name, role: 'merlin_or_morgana'}));
        break;
      case 'morgana':
        info.description = 'You are evil and can see other evil players (except Oberon)';
        info.sees = allPlayers.filter(p => ['assassin', 'mordred', 'minion'].includes(p.role))
          .map(p => ({id: p.id, name: p.name, role: 'evil'}));
        break;
      case 'assassin':
        info.description = 'You are evil and can see other evil players (except Oberon). You can assassinate Merlin if good wins';
        info.sees = allPlayers.filter(p => ['morgana', 'mordred', 'minion'].includes(p.role))
          .map(p => ({id: p.id, name: p.name, role: 'evil'}));
        break;
      case 'mordred':
        info.description = 'You are evil and can see other evil players (except Oberon). You are hidden from Merlin';
        info.sees = allPlayers.filter(p => ['morgana', 'assassin', 'minion'].includes(p.role))
          .map(p => ({id: p.id, name: p.name, role: 'evil'}));
        break;
      case 'minion':
        info.description = 'You are evil and can see other evil players (except Oberon)';
        info.sees = allPlayers.filter(p => ['morgana', 'assassin', 'mordred'].includes(p.role))
          .map(p => ({id: p.id, name: p.name, role: 'evil'}));
        break;
      case 'oberon':
        info.description = 'You are evil but hidden from other evil players and Merlin';
        break;
      default:
        info.description = 'You are a loyal servant of Arthur. Trust in Merlin\'s guidance';
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
      setError('');
      console.log('Creating session...');
      const response = await axios.post(`${API}/create-session`, {
        name: sessionName,
        player_name: playerName
      });
      console.log('Session created:', response.data);
      setSessionId(response.data.session_id);
      setPlayerId(response.data.player_id);
      
      // Fetch initial game state if WebSocket doesn't work
      setTimeout(fetchGameState, 1000);
    } catch (error) {
      console.error('Failed to create session:', error);
      setError('Failed to create session: ' + (error.response?.data?.detail || error.message));
    }
  };

  const joinSession = async () => {
    try {
      setError('');
      console.log('Joining session...');
      const response = await axios.post(`${API}/join-session`, {
        session_id: sessionIdInput,
        player_name: playerName
      });
      console.log('Joined session:', response.data);
      setSessionId(sessionIdInput);
      setPlayerId(response.data.player_id);
      
      // Fetch initial game state if WebSocket doesn't work
      setTimeout(fetchGameState, 1000);
    } catch (error) {
      console.error('Failed to join session:', error);
      setError('Failed to join session: ' + (error.response?.data?.detail || error.message));
    }
  };

  const startGame = async () => {
    try {
      await axios.post(`${API}/start-game`, {
        session_id: sessionId
      });
      setError('');
      // Fetch updated game state
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError('Failed to start game: ' + (error.response?.data?.detail || error.message));
    }
  };

  const startTestGame = async () => {
    try {
      await axios.post(`${API}/start-test-game`, {
        session_id: sessionId
      });
      setError('');
      // Fetch updated game state
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError('Failed to start test game: ' + (error.response?.data?.detail || error.message));
    }
  };

  const selectTeam = async () => {
    try {
      await axios.post(`${API}/select-team`, {
        session_id: sessionId,
        player_id: playerId,
        team_members: selectedTeam
      });
      setSelectedTeam([]);
      setError('');
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError('Failed to select team');
    }
  };

  const voteTeam = async (vote) => {
    try {
      await axios.post(`${API}/vote-team`, {
        session_id: sessionId,
        player_id: playerId,
        vote: vote
      });
      setError('');
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError('Failed to vote');
    }
  };

  const voteMission = async (vote) => {
    try {
      await axios.post(`${API}/vote-mission`, {
        session_id: sessionId,
        player_id: playerId,
        vote: vote
      });
      setError('');
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError('Failed to vote on mission');
    }
  };

  const useLadyOfLake = async () => {
    try {
      const response = await axios.post(`${API}/lady-of-lake`, {
        session_id: sessionId,
        player_id: playerId,
        target_player_id: ladyTarget
      });
      setLadyResult(response.data);
      setLadyTarget('');
      setError('');
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError('Failed to use Lady of the Lake');
    }
  };

  const assassinate = async () => {
    try {
      await axios.post(`${API}/assassinate`, {
        session_id: sessionId,
        player_id: playerId,
        target_player_id: assassinTarget
      });
      setAssassinTarget('');
      setError('');
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError('Failed to assassinate');
    }
  };

  const toggleLadyOfLake = async (enabled) => {
    try {
      await axios.post(`${API}/toggle-lady-of-lake`, {
        session_id: sessionId,
        enabled: enabled
      });
      setError('');
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError('Failed to toggle Lady of the Lake: ' + (error.response?.data?.detail || error.message));
    }
  };

  const restartGame = async () => {
    try {
      await axios.post(`${API}/restart-game`, {
        session_id: sessionId
      });
      setError('');
      setTimeout(fetchGameState, 500);
    } catch (error) {
      setError('Failed to restart game: ' + (error.response?.data?.detail || error.message));
    }
  };

  const toggleTeamMember = (playerIdToToggle) => {
    const currentMission = gameState?.current_mission_details;
    if (!currentMission) return;

    if (selectedTeam.includes(playerIdToToggle)) {
      setSelectedTeam(selectedTeam.filter(id => id !== playerIdToToggle));
    } else if (selectedTeam.length < currentMission.team_size) {
      setSelectedTeam([...selectedTeam, playerIdToToggle]);
    }
  };

  const getCurrentPlayer = () => {
    return gameState?.session?.players?.find(p => p.id === playerId);
  };

  const getCurrentLeader = () => {
    return gameState?.session?.players?.find(p => p.is_leader);
  };

  const isCurrentPlayerLeader = () => {
    return getCurrentPlayer()?.is_leader;
  };

  const hasPlayerVoted = (playerId, votes) => {
    return votes && votes.hasOwnProperty(playerId);
  };

  const renderLobby = () => {
    const players = gameState?.session?.players || [];
    const canStart = players.length >= 5;

    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-xl shadow-2xl p-8">
            <h1 className="text-4xl font-bold text-center mb-8 text-gray-800">
              🏰 The Resistance: Avalon
            </h1>
            
            <div className="text-center mb-8">
              <h2 className="text-2xl font-semibold text-gray-700 mb-4">
                Session: {gameState?.session?.name}
              </h2>
              <div className="bg-blue-100 rounded-lg p-4 mb-4">
                <p className="text-lg">Session ID: <span className="font-mono font-bold">{sessionId}</span></p>
                <p className="text-sm text-gray-600">Share this ID with your friends to join!</p>
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-8">
              <div className="bg-gray-50 rounded-lg p-6">
                <h3 className="text-xl font-bold mb-4 text-gray-700">
                  Players ({players.length}/10)
                </h3>
                <div className="space-y-2">
                  {players.map((player, index) => (
                    <div
                      key={player.id}
                      className={`flex items-center justify-between p-3 rounded-lg ${
                        player.id === playerId ? 'bg-blue-200' : 'bg-white'
                      }`}
                    >
                      <span className="font-medium">{player.name}</span>
                      <div className="flex items-center space-x-2">
                        {player.is_connected ? (
                          <span className="text-green-600 text-sm">🟢 Online</span>
                        ) : (
                          <span className="text-red-600 text-sm">🔴 Offline</span>
                        )}
                        {player.id === playerId && (
                          <span className="bg-blue-500 text-white px-2 py-1 rounded text-xs">You</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-6">
                <h3 className="text-xl font-bold mb-4 text-gray-700">Game Rules</h3>
                <div className="space-y-3 text-sm">
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
                    <p>If Good wins, Assassin can kill Merlin for Evil victory</p>
                  </div>
                  {players.length >= 7 && (
                    <div>
                      <h4 className="font-semibold">🌟 Lady of the Lake:</h4>
                      <p>Reveal a player's allegiance after missions 2 & 3</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-8 text-center">
              {canStart ? (
                <div className="space-y-4">
                  <button
                    onClick={startGame}
                    className="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-8 rounded-lg text-lg transition-colors mr-4"
                  >
                    🚀 Start Game
                  </button>
                  <div>
                    <button
                      onClick={startTestGame}
                      className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg transition-colors"
                    >
                      🧪 Start Test Game (adds bots)
                    </button>
                    <p className="text-xs text-gray-500 mt-1">Test mode adds bot players for testing</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="text-gray-600">
                    <p>Need at least 5 players to start</p>
                    <p>({5 - players.length} more needed)</p>
                  </div>
                  <button
                    onClick={startTestGame}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded-lg transition-colors"
                  >
                    🧪 Start Test Game (adds bots)
                  </button>
                  <p className="text-xs text-gray-500">Test mode adds bot players so you can try the game</p>
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
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="bg-white rounded-xl shadow-2xl p-6 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-800">🏰 {session.name}</h1>
                <p className="text-gray-600">Phase: {session.phase.replace('_', ' ').toUpperCase()}</p>
              </div>
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-yellow-500'}`}></div>
                  <span className="text-sm text-gray-600">
                    {isConnected ? 'Real-time' : 'Offline Mode'}
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
                <div className="text-center">
                  <p className="text-sm text-gray-600">Good Wins</p>
                  <p className="text-xl font-bold text-green-600">{session.good_wins}</p>
                </div>
                <div className="text-center">
                  <p className="text-sm text-gray-600">Evil Wins</p>
                  <p className="text-xl font-bold text-red-600">{session.evil_wins}</p>
                </div>
                <div className="text-center">
                  <p className="text-sm text-gray-600">Vote Track</p>
                  <p className="text-xl font-bold text-yellow-600">{session.vote_track}/5</p>
                </div>
              </div>
            </div>
          </div>

          <div className="grid lg:grid-cols-3 gap-6">
            {/* Left Panel - Game Info */}
            <div className="lg:col-span-2 space-y-6">
              {/* Role Info */}
              {roleInfo && (
                <div className="bg-white rounded-xl shadow-2xl p-6">
                  <h2 className="text-xl font-bold mb-4 text-gray-800">
                    🎭 Your Role: {roleInfo.role.replace('_', ' ').toUpperCase()}
                  </h2>
                  <div className={`p-4 rounded-lg ${
                    roleInfo.team === 'good' ? 'bg-blue-50 border-l-4 border-blue-500' : 'bg-red-50 border-l-4 border-red-500'
                  }`}>
                    <p className="font-medium mb-2">
                      Team: <span className={roleInfo.team === 'good' ? 'text-blue-600' : 'text-red-600'}>
                        {roleInfo.team.toUpperCase()}
                      </span>
                    </p>
                    <p className="text-sm text-gray-700 mb-3">{roleInfo.description}</p>
                    {roleInfo.sees && roleInfo.sees.length > 0 && (
                      <div>
                        <p className="font-medium text-sm mb-2">You can see:</p>
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
                </div>
              )}

              {/* Mission Info */}
              <div className="bg-white rounded-xl shadow-2xl p-6">
                <h2 className="text-xl font-bold mb-4 text-gray-800">📋 Missions</h2>
                <div className="grid grid-cols-5 gap-2 mb-4">
                  {session.missions.map((mission, index) => (
                    <div
                      key={index}
                      className={`p-3 rounded-lg text-center border-2 ${
                        index === session.current_mission
                          ? 'bg-yellow-100 border-yellow-500'
                          : mission.result === 'success'
                          ? 'bg-green-100 border-green-500'
                          : mission.result === 'fail'
                          ? 'bg-red-100 border-red-500'
                          : 'bg-gray-100 border-gray-300'
                      }`}
                    >
                      <div className="text-lg font-bold">#{mission.number}</div>
                      <div className="text-xs">
                        {mission.team_size} players
                      </div>
                      <div className="text-xs">
                        {mission.fails_required} fail{mission.fails_required > 1 ? 's' : ''} needed
                      </div>
                      {mission.result !== 'pending' && (
                        <div className={`text-xs font-bold ${
                          mission.result === 'success' ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {mission.result.toUpperCase()}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Current Mission Details */}
              {currentMission && (
                <div className="bg-white rounded-xl shadow-2xl p-6">
                  <h2 className="text-xl font-bold mb-4 text-gray-800">
                    🎯 Mission {currentMission.number}
                  </h2>
                  
                  {session.phase === 'mission_team_selection' && (
                    <div>
                      <p className="mb-4">
                        <strong>Leader:</strong> {currentLeader?.name} must select {currentMission.team_size} players
                      </p>
                      
                      {isCurrentPlayerLeader() && (
                        <div className="space-y-4">
                          <div className="grid grid-cols-2 gap-2">
                            {session.players.map((player) => (
                              <button
                                key={player.id}
                                onClick={() => toggleTeamMember(player.id)}
                                className={`p-3 rounded-lg border-2 transition-colors ${
                                  selectedTeam.includes(player.id)
                                    ? 'bg-blue-500 text-white border-blue-500'
                                    : 'bg-white border-gray-300 hover:border-blue-300'
                                }`}
                              >
                                {player.name}
                              </button>
                            ))}
                          </div>
                          
                          <div className="text-center">
                            <p className="mb-2">
                              Selected: {selectedTeam.length}/{currentMission.team_size}
                            </p>
                            <button
                              onClick={selectTeam}
                              disabled={selectedTeam.length !== currentMission.team_size}
                              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-bold py-2 px-6 rounded-lg transition-colors"
                            >
                              Propose Team
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {session.phase === 'mission_voting' && (
                    <div>
                      <p className="mb-4">
                        <strong>Proposed Team:</strong> {currentMission.team_members.map(id => 
                          session.players.find(p => p.id === id)?.name
                        ).join(', ')}
                      </p>
                      
                      <div className="mb-4">
                        <h4 className="font-semibold mb-2">Votes:</h4>
                        <div className="grid grid-cols-2 gap-2">
                          {session.players.map((player) => (
                            <div
                              key={player.id}
                              className={`p-2 rounded border ${
                                hasPlayerVoted(player.id, currentMission.votes)
                                  ? 'bg-blue-100 border-blue-300'
                                  : 'bg-gray-100 border-gray-300'
                              }`}
                            >
                              <span className="font-medium">{player.name}</span>
                              {hasPlayerVoted(player.id, currentMission.votes) && (
                                <span className="ml-2 text-sm">✓ Voted</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                      
                      {!hasPlayerVoted(playerId, currentMission.votes) && (
                        <div className="text-center space-x-4">
                          <button
                            onClick={() => voteTeam(true)}
                            className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-6 rounded-lg transition-colors"
                          >
                            ✓ Approve
                          </button>
                          <button
                            onClick={() => voteTeam(false)}
                            className="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-6 rounded-lg transition-colors"
                          >
                            ✗ Reject
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {session.phase === 'mission_execution' && (
                    <div>
                      <p className="mb-4">
                        <strong>Mission Team:</strong> {currentMission.team_members.map(id => 
                          session.players.find(p => p.id === id)?.name
                        ).join(', ')}
                      </p>
                      
                      {currentMission.team_members.includes(playerId) && (
                        <div>
                          <p className="mb-4 font-semibold">You are on this mission! Choose your action:</p>
                          
                          {!hasPlayerVoted(playerId, currentMission.mission_votes) && (
                            <div className="text-center space-x-4">
                              <button
                                onClick={() => voteMission(true)}
                                className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-6 rounded-lg transition-colors"
                              >
                                ✓ Success
                              </button>
                              {roleInfo?.team === 'evil' && (
                                <button
                                  onClick={() => voteMission(false)}
                                  className="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-6 rounded-lg transition-colors"
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
                        <div className="grid grid-cols-2 gap-2">
                          {currentMission.team_members.map((memberId) => {
                            const member = session.players.find(p => p.id === memberId);
                            return (
                              <div
                                key={memberId}
                                className={`p-2 rounded border ${
                                  hasPlayerVoted(memberId, currentMission.mission_votes)
                                    ? 'bg-blue-100 border-blue-300'
                                    : 'bg-gray-100 border-gray-300'
                                }`}
                              >
                                <span className="font-medium">{member?.name}</span>
                                {hasPlayerVoted(memberId, currentMission.mission_votes) && (
                                  <span className="ml-2 text-sm">✓ Voted</span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Lady of the Lake */}
              {session.phase === 'lady_of_the_lake' && (
                <div className="bg-white rounded-xl shadow-2xl p-6">
                  <h2 className="text-xl font-bold mb-4 text-gray-800">🌟 Lady of the Lake</h2>
                  
                  {currentPlayer.lady_of_the_lake && (
                    <div className="space-y-4">
                      <p className="font-semibold">You have the Lady of the Lake! Choose a player to reveal their allegiance:</p>
                      
                      <div className="grid grid-cols-2 gap-2">
                        {session.players.filter(p => p.id !== playerId).map((player) => (
                          <button
                            key={player.id}
                            onClick={() => setLadyTarget(player.id)}
                            className={`p-3 rounded-lg border-2 transition-colors ${
                              ladyTarget === player.id
                                ? 'bg-yellow-500 text-white border-yellow-500'
                                : 'bg-white border-gray-300 hover:border-yellow-300'
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
                            className="bg-yellow-600 hover:bg-yellow-700 text-white font-bold py-2 px-6 rounded-lg transition-colors"
                          >
                            Use Lady of the Lake
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                  
                  {ladyResult && (
                    <div className="mt-4 p-4 bg-yellow-50 rounded-lg">
                      <p className="font-semibold">
                        {ladyResult.target_name} is: <span className={ladyResult.allegiance === 'good' ? 'text-blue-600' : 'text-red-600'}>
                          {ladyResult.allegiance.toUpperCase()}
                        </span>
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Assassination Phase */}
              {session.phase === 'assassination' && (
                <div className="bg-white rounded-xl shadow-2xl p-6">
                  <h2 className="text-xl font-bold mb-4 text-gray-800">🗡️ Assassination</h2>
                  
                  {roleInfo?.role === 'assassin' && (
                    <div className="space-y-4">
                      <p className="font-semibold text-red-600">Good has won the missions, but you can still win by assassinating Merlin!</p>
                      
                      <div className="grid grid-cols-2 gap-2">
                        {session.players.filter(p => p.id !== playerId).map((player) => (
                          <button
                            key={player.id}
                            onClick={() => setAssassinTarget(player.id)}
                            className={`p-3 rounded-lg border-2 transition-colors ${
                              assassinTarget === player.id
                                ? 'bg-red-500 text-white border-red-500'
                                : 'bg-white border-gray-300 hover:border-red-300'
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
                            className="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-6 rounded-lg transition-colors"
                          >
                            Assassinate {session.players.find(p => p.id === assassinTarget)?.name}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                  
                  {roleInfo?.role !== 'assassin' && (
                    <p className="text-center text-gray-600">
                      The Assassin is choosing their target...
                    </p>
                  )}
                </div>
              )}

              {/* Game End */}
              {session.phase === 'game_end' && (
                <div className="bg-white rounded-xl shadow-2xl p-6">
                  <h2 className="text-xl font-bold mb-4 text-gray-800">🎉 Game Over!</h2>
                  
                  <div className="text-center">
                    <p className="text-2xl font-bold mb-4">
                      {session.game_result === 'good' ? (
                        <span className="text-blue-600">✓ GOOD WINS!</span>
                      ) : (
                        <span className="text-red-600">✗ EVIL WINS!</span>
                      )}
                    </p>
                    
                    <div className="mt-6">
                      <h3 className="font-semibold mb-2">Player Roles:</h3>
                      <div className="grid grid-cols-2 gap-2">
                        {session.players.map((player) => (
                          <div
                            key={player.id}
                            className={`p-2 rounded border ${
                              ['merlin', 'percival', 'loyal_servant'].includes(player.role)
                                ? 'bg-blue-100 border-blue-300'
                                : 'bg-red-100 border-red-300'
                            }`}
                          >
                            <span className="font-medium">{player.name}</span>
                            <span className="ml-2 text-sm">
                              ({player.role?.replace('_', ' ') || 'Unknown'})
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right Panel - Players */}
            <div className="bg-white rounded-xl shadow-2xl p-6">
              <h2 className="text-xl font-bold mb-4 text-gray-800">👥 Players</h2>
              
              <div className="space-y-2">
                {session.players.map((player) => (
                  <div
                    key={player.id}
                    className={`p-3 rounded-lg border-2 ${
                      player.id === playerId
                        ? 'bg-blue-100 border-blue-300'
                        : 'bg-gray-50 border-gray-200'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{player.name}</span>
                      <div className="flex items-center space-x-1">
                        {player.is_leader && (
                          <span className="text-yellow-600 text-sm">👑</span>
                        )}
                        {player.lady_of_the_lake && (
                          <span className="text-yellow-600 text-sm">🌟</span>
                        )}
                        {player.is_connected ? (
                          <span className="text-green-600 text-sm">🟢</span>
                        ) : (
                          <span className="text-red-600 text-sm">🔴</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderMainMenu = () => (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-2xl p-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">🏰 Avalon</h1>
          <p className="text-gray-600">The Resistance Board Game</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        {!isConnected && gameState && (
          <div className="mb-4 p-3 bg-yellow-100 border border-yellow-400 text-yellow-700 rounded-lg text-sm">
            ⚠️ Using offline mode - click refresh button or wait for auto-update (last update: {new Date(lastUpdate).toLocaleTimeString()})
          </div>
        )}

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Your Name
            </label>
            <input
              type="text"
              value={playerName}
              onChange={(e) => setPlayerName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="Enter your name..."
            />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Create New Session
              </label>
              <input
                type="text"
                value={sessionName}
                onChange={(e) => setSessionName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 mb-2"
                placeholder="Session name..."
              />
              <button
                onClick={createSession}
                disabled={!playerName || !sessionName}
                className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded-lg transition-colors"
              >
                Create Session
              </button>
            </div>

            <div className="text-center text-gray-500">
              <span>or</span>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Join Existing Session
              </label>
              <input
                type="text"
                value={sessionIdInput}
                onChange={(e) => setSessionIdInput(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 mb-2"
                placeholder="Session ID..."
              />
              <button
                onClick={joinSession}
                disabled={!playerName || !sessionIdInput}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded-lg transition-colors"
              >
                Join Session
              </button>
            </div>
          </div>
        </div>

        <div className="mt-8 text-center text-sm text-gray-500">
          <p>🎭 Social deduction game for 5-10 players</p>
          <p>Complete missions as Good or sabotage as Evil</p>
        </div>
      </div>
    </div>
  );

  if (!gameState) {
    return renderMainMenu();
  }

  if (gameState.session?.phase === 'lobby') {
    return renderLobby();
  }

  return renderGame();
}

export default App;