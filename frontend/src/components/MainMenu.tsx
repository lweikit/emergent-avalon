import React, { useState } from "react";
import api from "../api";
import { AxiosErrorResponse } from "../types";
import RuleBook from "./RuleBook";

interface MainMenuProps {
  onJoined: (sessionId: string, playerId: string, playerToken: string) => void;
  onSpectate: (sessionId: string, playerName?: string) => void | Promise<void>;
  spectatorError?: string | null;
}

const INPUT_CLASS =
  "w-full px-3 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-400";
const LABEL_CLASS = "block text-sm font-medium text-gray-300 mb-2";

export default function MainMenu({ onJoined, onSpectate, spectatorError }: MainMenuProps) {
  const [playerName, setPlayerName] = useState("");
  const [sessionName, setSessionName] = useState("");
  const [sessionIdInput, setSessionIdInput] = useState("");
  const [spectateIdInput, setSpectateIdInput] = useState("");
  const [spectateNameInput, setSpectateNameInput] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const hasName = !!playerName.trim();

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

  // Spectating is resolved by the parent, so this drives the same loading flag
  // to stop a second tap from creating a second spectator player.
  const spectate = async () => {
    setLoading(true);
    setError("");
    try {
      await onSpectate(spectateIdInput.trim(), spectateNameInput.trim() || undefined);
    } finally {
      setLoading(false);
    }
  };

  const submit = (fn: () => void, enabled: boolean) => (e: React.FormEvent) => {
    e.preventDefault();
    if (enabled && !loading) fn();
  };

  const canCreate = hasName && !!sessionName.trim();
  const canJoin = hasName && !!sessionIdInput.trim();
  const canSpectate = !!spectateIdInput.trim();

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-gray-900/90 backdrop-blur rounded-xl shadow-2xl p-4 sm:p-8 border border-gray-700">
        <div className="text-center mb-8">
          <h1 className="text-2xl sm:text-4xl font-bold text-white mb-2">Avalon</h1>
          <p className="text-xs sm:text-sm text-gray-400">The Resistance Board Game</p>
        </div>

        {error && (
          <div role="alert" className="mb-6 p-3 bg-red-900/40 border border-red-500 text-red-200 rounded-lg text-xs sm:text-sm flex items-start gap-2">
            <span className="flex-1">{error}</span>
            <button type="button" onClick={() => setError("")} aria-label="Dismiss error"
              className="text-red-200 hover:text-white px-1 leading-none">&times;</button>
          </div>
        )}

        <div className="space-y-4 sm:space-y-6">
          <div>
            <label htmlFor="player-name" className={LABEL_CLASS}>Your Name</label>
            <input id="player-name" type="text" value={playerName} onChange={(e) => setPlayerName(e.target.value)}
              autoComplete="nickname" maxLength={20} className={INPUT_CLASS}
              placeholder="Enter your name..." />
            {!hasName && (
              <p className="mt-1.5 text-xs text-gray-400">Enter a name to create or join a session.</p>
            )}
          </div>

          <div className="space-y-4">
            <form onSubmit={submit(createSession, canCreate)}>
              <label htmlFor="session-name" className={LABEL_CLASS}>Create New Session</label>
              <input id="session-name" type="text" value={sessionName} onChange={(e) => setSessionName(e.target.value)}
                maxLength={40} className={`${INPUT_CLASS} mb-2`} placeholder="Session name..." />
              <button type="submit" disabled={!canCreate || loading}
                className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 disabled:text-gray-300 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                {loading ? "Creating..." : "Create Session"}
              </button>
            </form>

            <div className="text-center text-gray-400 text-xs sm:text-sm"><span>or</span></div>

            <form onSubmit={submit(joinSession, canJoin)}>
              <label htmlFor="session-id" className={LABEL_CLASS}>Join Existing Session</label>
              <input id="session-id" type="text" value={sessionIdInput} onChange={(e) => setSessionIdInput(e.target.value)}
                autoCapitalize="characters" autoCorrect="off" spellCheck={false}
                className={`${INPUT_CLASS} mb-2 font-mono tracking-wider`} placeholder="Room code, e.g. KQ7MPZ" />
              <button type="submit" disabled={!canJoin || loading}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-300 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                {loading ? "Joining..." : "Join Session"}
              </button>
            </form>
          </div>
        </div>

        <form onSubmit={submit(spectate, canSpectate)} className="mt-4 pt-4 border-t border-gray-700">
          <h2 className="text-sm font-medium text-gray-300 mb-2">Spectate</h2>
          <p className="text-xs text-gray-400 mb-2">Watch the game on the board view. Best on a tablet. Name is optional.</p>
          {spectatorError && (
            <div role="alert" className="mb-2 p-2 bg-red-900/40 border border-red-500 text-red-200 rounded-lg text-xs">{spectatorError}</div>
          )}
          <label htmlFor="spectate-name" className="sr-only">Your name for spectating (optional)</label>
          <input id="spectate-name" type="text" value={spectateNameInput} onChange={(e) => setSpectateNameInput(e.target.value)}
            autoComplete="nickname" maxLength={20} className={`${INPUT_CLASS} mb-2`}
            placeholder="Your name (optional)" />
          <label htmlFor="spectate-id" className="sr-only">Room code to spectate</label>
          <input id="spectate-id" type="text" value={spectateIdInput} onChange={(e) => setSpectateIdInput(e.target.value)}
            autoCapitalize="characters" autoCorrect="off" spellCheck={false}
            className={`${INPUT_CLASS} mb-2 font-mono tracking-wider`} placeholder="Room code, e.g. KQ7MPZ" />
          <button type="submit" disabled={!canSpectate || loading}
            className="w-full bg-amber-600 hover:bg-amber-700 disabled:bg-gray-700 disabled:text-gray-300 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
            {loading ? "Connecting..." : "Watch Game"}
          </button>
        </form>

        <div className="mt-6">
          <RuleBook />
        </div>
      </div>
    </div>
  );
}
