import React, { useState, useEffect, useCallback } from "react";
import "./App.css";
import api from "./api";
import useWebSocket from "./hooks/useWebSocket";
import MainMenu from "./components/MainMenu";
import Lobby from "./components/Lobby";
import GameBoard from "./components/GameBoard";
import SpectatorBoard from "./components/SpectatorBoard";
import { GameState, GamePhase } from "./types";

const STORAGE_KEY = "avalon_session";
const SPECTATOR_KEY = "avalon_spectator";

interface SpectatorSession {
  sessionId: string;
  playerId: string | null;
  playerToken: string | null;
}

function loadSession(): { sessionId: string; playerId: string; playerToken: string } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (data.sessionId && data.playerId && data.playerToken) return data;
  } catch { /* ignore */ }
  return null;
}

function loadSpectatorSession(): SpectatorSession | null {
  try {
    const raw = localStorage.getItem(SPECTATOR_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (data.sessionId) return data;
  } catch { /* ignore */ }
  return null;
}

function saveSession(sessionId: string, playerId: string, playerToken: string) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ sessionId, playerId, playerToken }));
}

function clearSession() {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(SPECTATOR_KEY);
}

function App() {
  const saved = loadSession();
  const savedSpectator = loadSpectatorSession();
  const [sessionId, setSessionId] = useState<string | null>(saved?.sessionId ?? savedSpectator?.sessionId ?? null);
  const [playerId, setPlayerId] = useState<string | null>(saved?.playerId ?? savedSpectator?.playerId ?? null);
  const [playerToken, setPlayerToken] = useState<string | null>(saved?.playerToken ?? savedSpectator?.playerToken ?? null);
  const [spectatorMode, setSpectatorMode] = useState<boolean>(!!savedSpectator && !saved);
  const [spectatorError, setSpectatorError] = useState<string | null>(null);

  const { isConnected, gameState: wsGameState } = useWebSocket(sessionId, playerId, playerToken);

  // Fallback polling with personalized endpoint (includes role info)
  const [polledState, setPolledState] = useState<GameState | null>(null);

  const resetToMenu = useCallback(() => {
    clearSession();
    setSessionId(null);
    setPlayerId(null);
    setPlayerToken(null);
    setPolledState(null);
    setSpectatorMode(false);
  }, []);

  const fetchGameState = useCallback(async () => {
    if (!sessionId || !playerId || !playerToken || spectatorMode) return;
    try {
      const res = await api.getSessionPersonalized(sessionId, playerId, playerToken);
      setPolledState(res.data);
    } catch {
      resetToMenu();
    }
  }, [sessionId, playerId, playerToken, spectatorMode, resetToMenu]);

  useEffect(() => {
    if (sessionId && !isConnected && !spectatorMode) {
      fetchGameState();
      const interval = setInterval(fetchGameState, 2000);
      return () => clearInterval(interval);
    }
  }, [sessionId, isConnected, spectatorMode, fetchGameState]);

  const gameState = wsGameState || polledState;

  // Safety check: if we have a game state but the player is not in the session,
  // the saved session is stale — clear it and show the menu.
  const playerInSession = gameState?.session?.players?.some((p) => p.id === playerId);
  const effectiveState = spectatorMode ? gameState : (playerInSession ? gameState : null);

  useEffect(() => {
    if (!spectatorMode && gameState && !playerInSession && sessionId) {
      resetToMenu();
    }
  }, [spectatorMode, gameState, playerInSession, sessionId, resetToMenu]);

  // Spectator timeout: if no state arrives within 6s, bail back to menu
  useEffect(() => {
    if (!spectatorMode || effectiveState || spectatorError) return;
    const timer = setTimeout(() => {
      resetToMenu();
      setSpectatorError("Could not find session. Check the ID and try again.");
    }, 6000);
    return () => clearTimeout(timer);
  }, [spectatorMode, effectiveState, spectatorError, resetToMenu]);

  // Clear spectator error on successful state
  useEffect(() => {
    if (spectatorMode && effectiveState) {
      setSpectatorError(null);
    }
  }, [spectatorMode, effectiveState]);

  const handleLeave = useCallback(async () => {
    if (sessionId && playerId && playerToken) {
      try { await api.leaveSession(sessionId, playerId, playerToken); } catch { /* ignore */ }
    }
    resetToMenu();
  }, [sessionId, playerId, playerToken, resetToMenu]);

  const handleJoined = (sid: string, pid: string, token: string) => {
    setSessionId(sid);
    setPlayerId(pid);
    setPlayerToken(token);
    setSpectatorMode(false);
    setSpectatorError(null);
    localStorage.removeItem(SPECTATOR_KEY);
    saveSession(sid, pid, token);
  };

  const handleSpectate = async (sid: string, playerName?: string) => {
    clearSession();
    setSpectatorError(null);

    let resolvedSid = sid;
    let pid: string | null = null;
    let token: string | null = null;

    if (playerName) {
      try {
        const res = await api.joinSession(sid, playerName, true);
        resolvedSid = res.data.session_id;
        pid = res.data.player_id;
        token = res.data.player_token;
      } catch {
        setSpectatorError("Failed to join session. Check the session ID.");
        return;
      }
    }

    setSessionId(resolvedSid);
    setPlayerId(pid);
    setPlayerToken(token);
    setSpectatorMode(true);
    localStorage.setItem(SPECTATOR_KEY, JSON.stringify({ sessionId: resolvedSid, playerId: pid, playerToken: token }));
  };

  if (spectatorMode && effectiveState) {
    return <SpectatorBoard gameState={effectiveState} isConnected={isConnected} onLeave={handleLeave} />;
  }

  if (spectatorMode && !effectiveState && !spectatorError) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <p className="text-xl text-gray-300 mb-2">Connecting to session...</p>
          <p className="text-sm text-gray-500">Session ID: {sessionId?.slice(0, 8)}...</p>
        </div>
      </div>
    );
  }

  if (!effectiveState) {
    return <MainMenu onJoined={handleJoined} onSpectate={handleSpectate} spectatorError={spectatorError} />;
  }

  if (effectiveState.session?.phase === GamePhase.LOBBY) {
    return <Lobby session={effectiveState.session} playerId={playerId} isConnected={isConnected} onLeave={handleLeave} />;
  }

  return <GameBoard gameState={effectiveState} playerId={playerId} playerToken={playerToken} isConnected={isConnected} onLeave={handleLeave} />;
}

export default App;
