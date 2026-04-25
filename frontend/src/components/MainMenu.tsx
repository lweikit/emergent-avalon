import React, { useState } from "react";
import api from "../api";
import { AxiosErrorResponse } from "../types";
import RuleBook from "./RuleBook";

interface MainMenuProps {
  onJoined: (sessionId: string, playerId: string, playerToken: string) => void;
  onSpectate: (sessionId: string, playerName?: string) => void;
  spectatorError?: string | null;
}

export default function MainMenu({ onJoined, onSpectate, spectatorError }: MainMenuProps) {
  const [playerName, setPlayerName] = useState("");
  const [sessionName, setSessionName] = useState("");
  const [sessionIdInput, setSessionIdInput] = useState("");
  const [spectateIdInput, setSpectateIdInput] = useState("");
  const [spectateNameInput, setSpectateNameInput] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const createSession = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.createSession(sessionName.trim(), playerName.trim());
      onJoined(res.data.session_id, res.data.player_id, res.data.player_token);
    } catch (e) {
      const err = e as AxiosErrorResponse;
      setError("Failed to create session: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const joinSession = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.joinSession(sessionIdInput.trim(), playerName.trim(), false);
      onJoined(res.data.session_id, res.data.player_id, res.data.player_token);
    } catch (e) {
      const err = e as AxiosErrorResponse;
      setError("Failed to join session: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-gray-900/90 backdrop-blur rounded-xl shadow-2xl p-4 sm:p-8 border border-gray-700">
        <div className="text-center mb-8">
          <h1 className="text-2xl sm:text-4xl font-bold text-white mb-2">Avalon</h1>
          <p className="text-xs sm:text-sm text-gray-400">The Resistance Board Game</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-900/40 border border-red-500 text-red-300 rounded-lg text-xs sm:text-sm">{error}</div>
        )}

        <div className="space-y-4 sm:space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Your Name</label>
            <input type="text" value={playerName} onChange={(e) => setPlayerName(e.target.value)}
              className="w-full px-3 py-3 bg-gray-800 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm text-white placeholder-gray-500"
              placeholder="Enter your name..." />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Create New Session</label>
              <input type="text" value={sessionName} onChange={(e) => setSessionName(e.target.value)}
                className="w-full px-3 py-3 bg-gray-800 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 mb-2 text-sm text-white placeholder-gray-500"
                placeholder="Session name..." />
              <button onClick={createSession} disabled={!playerName.trim() || !sessionName.trim() || loading}
                className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 disabled:text-gray-500 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                {loading ? "Creating..." : "Create Session"}
              </button>
            </div>

            <div className="text-center text-gray-500 text-xs sm:text-sm"><span>or</span></div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Join Existing Session</label>
              <input type="text" value={sessionIdInput} onChange={(e) => setSessionIdInput(e.target.value)}
                className="w-full px-3 py-3 bg-gray-800 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 mb-2 text-sm text-white placeholder-gray-500"
                placeholder="Session ID..." />
              <button onClick={joinSession} disabled={!playerName.trim() || !sessionIdInput.trim() || loading}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                {loading ? "Joining..." : "Join Session"}
              </button>
            </div>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-gray-700">
          <label className="block text-sm font-medium text-gray-300 mb-2">Spectate</label>
          <p className="text-xs text-gray-500 mb-2">Watch the game on the board view. Name is optional.</p>
          {spectatorError && (
            <div className="mb-2 p-2 bg-red-900/40 border border-red-500 text-red-300 rounded-lg text-xs">{spectatorError}</div>
          )}
          <input type="text" value={spectateNameInput} onChange={(e) => setSpectateNameInput(e.target.value)}
            className="w-full px-3 py-3 bg-gray-800 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 mb-2 text-sm text-white placeholder-gray-500"
            placeholder="Your name (optional)" />
          <input type="text" value={spectateIdInput} onChange={(e) => setSpectateIdInput(e.target.value)}
            className="w-full px-3 py-3 bg-gray-800 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 mb-2 text-sm text-white placeholder-gray-500"
            placeholder="Session ID..." />
          <button onClick={() => onSpectate(spectateIdInput.trim(), spectateNameInput.trim() || undefined)} disabled={!spectateIdInput.trim() || loading}
            className="w-full bg-amber-600 hover:bg-amber-700 disabled:bg-gray-700 disabled:text-gray-500 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
            {loading ? "Connecting..." : "Watch Game"}
          </button>
        </div>

        <div className="mt-6">
          <RuleBook />
        </div>
      </div>
    </div>
  );
}
