import api from "../api";
import { Session, optionalEvilSlots } from "../types";
import useAsyncAction from "../hooks/useAsyncAction";
import RuleBook from "./RuleBook";
import CopyCodeButton from "./CopyCodeButton";

interface LobbyProps {
  session: Session;
  playerId: string | null;
  isConnected: boolean;
  onLeave: () => void;
}

interface SettingToggleProps {
  name: string;
  description: string;
  enabled: boolean;
  onToggle: () => void;
  unavailableReason?: string | null;
  activeColor: string;
}

function SettingToggle({ name, description, enabled, onToggle, unavailableReason, activeColor }: SettingToggleProps) {
  const disabled = !!unavailableReason;
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <h4 className={`font-semibold text-sm ${disabled ? "text-gray-400" : "text-gray-200"}`}>{name}</h4>
        <p className="text-xs text-gray-400">{unavailableReason || description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={enabled && !disabled}
        aria-label={name}
        onClick={onToggle}
        disabled={disabled}
        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex-shrink-0 min-h-[36px] ${
          disabled
            ? "bg-gray-800 text-gray-500 cursor-not-allowed"
            : enabled
            ? `${activeColor} text-white`
            : "bg-gray-700 hover:bg-gray-600 text-gray-200"
        }`}
      >
        {enabled && !disabled ? "On" : "Off"}
      </button>
    </div>
  );
}

export default function Lobby({ session, playerId, isConnected, onLeave }: LobbyProps) {
  const { execute, error, clearError } = useAsyncAction();
  const players = session.players || [];
  const activePlayers = players.filter((p) => !p.is_spectator);
  const spectators = players.filter((p) => p.is_spectator);
  const canStart = activePlayers.length >= 5;
  const currentPlayer = players.find((p) => p.id === playerId);
  const displayCode = session.code || session.id.slice(0, 8);

  const startGame = () => execute(() => api.startGame(session.id));
  const startTestGame = () => execute(() => api.startTestGame(session.id));
  const toggleLady = () => execute(() => api.toggleLadyOfLake(session.id, !session.lady_of_the_lake_enabled));
  const toggleMordred = () => execute(() => api.toggleMordred(session.id, !session.mordred_enabled));
  const toggleOberon = () => execute(() => api.toggleOberon(session.id, !session.oberon_enabled));

  // Only so many optional evil roles fit at a given player count, and the
  // backend fills them Mordred-first. Say so rather than showing a toggle that
  // silently won't apply.
  const slots = optionalEvilSlots(activePlayers.length);
  const mordredUnavailable = slots < 1 ? "Needs 7+ players" : null;
  const oberonUnavailable =
    slots < 1
      ? "Needs 7+ players"
      : slots === 1 && session.mordred_enabled
      ? `Only one optional evil role fits at ${activePlayers.length} players — Mordred has the slot`
      : null;
  const ladyUnavailable = activePlayers.length < 7 ? "Needs 7+ players" : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 p-4">
      <div className="max-w-6xl mx-auto px-4">
        <div className="bg-gray-900/90 backdrop-blur rounded-xl shadow-2xl p-4 sm:p-8 border border-gray-700">
          <div className="text-center mb-6">
            <h1 className="text-xl sm:text-2xl md:text-4xl font-bold text-white mb-2">{session.name}</h1>
            <p className="text-xs sm:text-sm text-gray-400">Waiting for players to join...</p>
            <div className="mt-2 flex flex-wrap justify-center items-center gap-2 text-xs sm:text-sm">
              <CopyCodeButton code={displayCode} />
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500 animate-pulse"}`} aria-hidden="true" />
                <span className="text-gray-300">{isConnected ? "LIVE" : "OFFLINE"}</span>
              </div>
              <button type="button" onClick={onLeave} className="text-gray-300 hover:text-white px-3 py-2 rounded transition-colors text-xs min-h-[44px]">
                Leave
              </button>
            </div>
          </div>

          {error && (
            <div role="alert" className="mb-4 p-3 bg-red-900/40 border border-red-500 text-red-200 rounded-lg text-xs sm:text-sm flex items-start gap-2">
              <span className="flex-1">{error}</span>
              <button type="button" onClick={clearError} aria-label="Dismiss error"
                className="text-red-200 hover:text-white px-1 leading-none">&times;</button>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
            <div className="bg-gray-800 rounded-lg p-4 sm:p-6 border border-gray-700">
              <h2 className="text-base sm:text-lg font-bold mb-4 text-white">Active Players ({activePlayers.length}/10)</h2>
              <div className="space-y-2">
                {activePlayers.map((player) => (
                  <div key={player.id} className={`flex items-center justify-between p-2 sm:p-3 rounded-lg text-xs sm:text-sm ${player.id === playerId ? "bg-blue-900/30 border border-blue-500" : "bg-gray-700/50 border border-gray-600"}`}>
                    <span className={`font-medium truncate flex-1 ${player.is_connected ? "text-white" : "text-gray-400 italic"}`}>
                      {player.name}
                    </span>
                    <div className="flex items-center space-x-2 flex-shrink-0">
                      <span className={`w-2 h-2 rounded-full ${player.is_connected ? "bg-green-500" : "bg-red-500"}`} aria-hidden="true" />
                      <span className="sr-only">{player.is_connected ? "connected" : "disconnected"}</span>
                      {player.is_bot && <span className="text-purple-300 text-xs">Bot</span>}
                      {player.id === playerId && <span className="bg-blue-600 text-white px-2 py-1 rounded text-xs">You</span>}
                    </div>
                  </div>
                ))}
              </div>
              {spectators.length > 0 && (
                <div className="mt-4">
                  <h3 className="text-xs font-semibold text-gray-400 mb-2">Spectators ({spectators.length})</h3>
                  <div className="space-y-1">
                    {spectators.map((player) => (
                      <div key={player.id} className={`flex items-center justify-between p-2 rounded-lg text-xs ${player.id === playerId ? "bg-purple-900/30 border border-purple-500" : "bg-gray-700/50 border border-gray-600"}`}>
                        <span className="font-medium truncate flex-1 text-gray-300">{player.name}</span>
                        {player.id === playerId && <span className="bg-purple-600 text-white px-2 py-1 rounded text-xs">You</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-6">
              <div className="bg-gray-800 rounded-lg p-4 sm:p-6 border border-gray-700">
                <h2 className="text-base sm:text-lg font-bold mb-4 text-white">Game Settings</h2>
                <div className="space-y-3">
                  <SettingToggle
                    name="Mordred" description="Evil, hidden from Merlin"
                    enabled={session.mordred_enabled} onToggle={toggleMordred}
                    unavailableReason={mordredUnavailable} activeColor="bg-red-600 hover:bg-red-700"
                  />
                  <SettingToggle
                    name="Oberon" description="Evil, hidden from everyone"
                    enabled={session.oberon_enabled} onToggle={toggleOberon}
                    unavailableReason={oberonUnavailable} activeColor="bg-red-600 hover:bg-red-700"
                  />
                  <SettingToggle
                    name="Lady of the Lake" description="Reveal allegiances after missions 2, 3 and 4"
                    enabled={session.lady_of_the_lake_enabled} onToggle={toggleLady}
                    unavailableReason={ladyUnavailable} activeColor="bg-yellow-600 hover:bg-yellow-700"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 text-center">
            {canStart && !currentPlayer?.is_spectator ? (
              <div className="space-y-4">
                <button type="button" onClick={startGame} className="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-6 rounded-lg text-base sm:text-lg transition-colors w-full sm:w-auto min-h-[48px]">
                  Start Game
                </button>
                <div>
                  <button type="button" onClick={startTestGame} className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 sm:px-6 rounded-lg transition-colors w-full sm:w-auto">
                    Start Test Game (adds bots)
                  </button>
                </div>
              </div>
            ) : currentPlayer?.is_spectator ? (
              <p className="text-gray-300">You are spectating. Waiting for players to start...</p>
            ) : (
              <div className="space-y-4">
                <p className="text-gray-300">Need at least 5 players ({5 - activePlayers.length} more needed)</p>
                <button type="button" onClick={startTestGame} className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition-colors w-full sm:w-auto min-h-[48px]">
                  Start Test Game (adds bots)
                </button>
              </div>
            )}
          </div>

          <div className="mt-6">
            <RuleBook />
          </div>
        </div>
      </div>
    </div>
  );
}
