import React, { useState } from "react";
import api from "../api";
import RuleBook from "./RuleBook";

interface MainMenuProps {
  onJoined: (sessionId: string, playerId: string, playerToken: string) => void;
}

interface AxiosErrorResponse {
  response?: {
    data?: {
      detail?: string;
    };
  };
  message: string;
}

export default function MainMenu({ onJoined }: MainMenuProps) {
  const [playerName, setPlayerName] = useState("");
  const [sessionName, setSessionName] = useState("");
  const [sessionIdInput, setSessionIdInput] = useState("");
  const [joinAsSpectator, setJoinAsSpectator] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const createSession = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.createSession(sessionName, playerName);
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
      const res = await api.joinSession(sessionIdInput, playerName, joinAsSpectator);
      onJoined(sessionIdInput, res.data.player_id, res.data.player_token);
    } catch (e) {
      const err = e as AxiosErrorResponse;
      setError("Failed to join session: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-2xl p-4 sm:p-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl sm:text-4xl font-bold text-gray-800 mb-2">Avalon</h1>
          <p className="text-xs sm:text-sm text-gray-600">The Resistance Board Game</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-100 border border-red-400 text-red-700 rounded-lg text-xs sm:text-sm">{error}</div>
        )}

        <div className="space-y-4 sm:space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Your Name</label>
            <input type="text" value={playerName} onChange={(e) => setPlayerName(e.target.value)}
              className="w-full px-3 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
              placeholder="Enter your name..." />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Create New Session</label>
              <input type="text" value={sessionName} onChange={(e) => setSessionName(e.target.value)}
                className="w-full px-3 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 mb-2 text-sm"
                placeholder="Session name..." />
              <button onClick={createSession} disabled={!playerName || !sessionName || loading}
                className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                {loading ? "Creating..." : "Create Session"}
              </button>
            </div>

            <div className="text-center text-gray-500 text-xs sm:text-sm"><span>or</span></div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Join Existing Session</label>
              <input type="text" value={sessionIdInput} onChange={(e) => setSessionIdInput(e.target.value)}
                className="w-full px-3 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 mb-2 text-sm"
                placeholder="Session ID..." />
              <div className="mb-2">
                <label className="flex items-center space-x-2">
                  <input type="checkbox" checked={joinAsSpectator} onChange={(e) => setJoinAsSpectator(e.target.checked)} className="rounded" />
                  <span className="text-xs sm:text-sm text-gray-700">Join as spectator (watch only)</span>
                </label>
              </div>
              <button onClick={joinSession} disabled={!playerName || !sessionIdInput || loading}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                {loading ? "Joining..." : joinAsSpectator ? "Join as Spectator" : "Join Session"}
              </button>
            </div>
          </div>
        </div>

        <div className="mt-6">
          <RuleBook />
        </div>
      </div>
    </div>
  );
}
