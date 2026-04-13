import React, { useState, useEffect, useCallback } from "react";
import "./App.css";
import api from "./api";
import useWebSocket from "./hooks/useWebSocket";
import MainMenu from "./components/MainMenu";
import Lobby from "./components/Lobby";
import GameBoard from "./components/GameBoard";
import { GameState } from "./types";

const STORAGE_KEY = "avalon_session";

function loadSession(): { sessionId: string; playerId: string; playerToken: string } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (data.sessionId && data.playerId && data.playerToken) return data;
  } catch { /* ignore */ }
  return null;
}

function saveSession(sessionId: string, playerId: string, playerToken: string) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ sessionId, playerId, playerToken }));
}

function clearSession() {
  localStorage.removeItem(STORAGE_KEY);
}

function App() {
  const saved = loadSession();
  const [sessionId, setSessionId] = useState<string | null>(saved?.sessionId ?? null);
  const [playerId, setPlayerId] = useState<string | null>(saved?.playerId ?? null);
  const [playerToken, setPlayerToken] = useState<string | null>(saved?.playerToken ?? null);

  const { isConnected, gameState: wsGameState } = useWebSocket(sessionId, playerId, playerToken);

  // Fallback polling with personalized endpoint (includes role info)
  const [polledState, setPolledState] = useState<GameState | null>(null);

  const resetToMenu = useCallback(() => {
    clearSession();
    setSessionId(null);
    setPlayerId(null);
    setPlayerToken(null);
    setPolledState(null);
  }, []);

  const fetchGameState = useCallback(async () => {
    if (!sessionId || !playerId || !playerToken) return;
    try {
      const res = await api.getSessionPersonalized(sessionId, playerId, playerToken);
      setPolledState(res.data);
    } catch {
      // Token invalid or session gone — clear and go to menu
      resetToMenu();
    }
  }, [sessionId, playerId, playerToken, resetToMenu]);

  useEffect(() => {
    if (sessionId && !isConnected) {
      fetchGameState();
      const interval = setInterval(fetchGameState, 2000);
      return () => clearInterval(interval);
    }
  }, [sessionId, isConnected, fetchGameState]);

  const gameState = wsGameState || polledState;

  // Safety check: if we have a game state but the player is not in the session,
  // the saved session is stale — clear it and show the menu.
  const playerInSession = gameState?.session?.players?.some((p) => p.id === playerId);
  const effectiveState = playerInSession ? gameState : null;

  useEffect(() => {
    if (gameState && !playerInSession && sessionId) {
      resetToMenu();
    }
  }, [gameState, playerInSession, sessionId, resetToMenu]);

  const handleJoined = (sid: string, pid: string, token: string) => {
    setSessionId(sid);
    setPlayerId(pid);
    setPlayerToken(token);
    saveSession(sid, pid, token);
  };

  if (!effectiveState) {
    return <MainMenu onJoined={handleJoined} />;
  }

  if (effectiveState.session?.phase === "lobby") {
    return <Lobby session={effectiveState.session} playerId={playerId} isConnected={isConnected} onLeave={resetToMenu} />;
  }

  return <GameBoard gameState={effectiveState} playerId={playerId} playerToken={playerToken} isConnected={isConnected} onLeave={resetToMenu} />;
}

export default App;
