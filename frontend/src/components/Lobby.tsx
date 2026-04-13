import api from "../api";
import { Session } from "../types";
import RuleBook from "./RuleBook";

interface LobbyProps {
  session: Session;
  playerId: string | null;
  isConnected: boolean;
}

export default function Lobby({ session, playerId, isConnected }: LobbyProps) {
  const players = session.players || [];
  const activePlayers = players.filter((p) => !p.is_spectator);
  const spectators = players.filter((p) => p.is_spectator);
  const canStart = activePlayers.length >= 5;
  const currentPlayer = players.find((p) => p.id === playerId);

  const startGame = async () => {
    try { await api.startGame(session.id); } catch (_) {}
  };
  const startTestGame = async () => {
    try { await api.startTestGame(session.id); } catch (_) {}
  };
  const toggleLady = async () => {
    try { await api.toggleLadyOfLake(session.id, !session.lady_of_the_lake_enabled); } catch (_) {}
  };
  const toggleMordred = async () => {
    try { await api.toggleMordred(session.id, !session.mordred_enabled); } catch (_) {}
  };
  const toggleOberon = async () => {
    try { await api.toggleOberon(session.id, !session.oberon_enabled); } catch (_) {}
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 p-4">
      <div className="max-w-6xl mx-auto px-4">
        <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-8">
          <div className="text-center mb-6">
            <h1 className="text-xl sm:text-2xl md:text-4xl font-bold text-gray-800 mb-2">{session.name}</h1>
            <p className="text-xs sm:text-sm text-gray-600">Waiting for players to join...</p>
            <div className="mt-2 flex flex-wrap justify-center items-center gap-2 text-xs sm:text-sm">
              <button onClick={() => navigator.clipboard.writeText(session.id)}
                className="bg-blue-100 hover:bg-blue-200 text-blue-800 px-3 py-2 rounded transition-colors min-h-[44px]"
                title="Tap to copy full session ID">
                Session ID: {session.id.slice(0, 8)}...
              </button>
              <span className={`px-2 py-1 rounded ${isConnected ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
                {isConnected ? "Connected" : "Offline"}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
            <div className="bg-gray-50 rounded-lg p-4 sm:p-6">
              <h3 className="text-base sm:text-lg font-bold mb-4 text-gray-700">Active Players ({activePlayers.length}/10)</h3>
              <div className="space-y-2">
                {activePlayers.map((player) => (
                  <div key={player.id} className={`flex items-center justify-between p-2 sm:p-3 rounded-lg text-xs sm:text-sm ${player.id === playerId ? "bg-blue-200" : "bg-white"}`}>
                    <span className="font-medium truncate flex-1">{player.name}</span>
                    <div className="flex items-center space-x-2 flex-shrink-0">
                      <span className={`text-xs ${player.is_connected ? "text-green-600" : "text-red-600"}`}>
                        {player.is_connected ? "Online" : "Offline"}
                      </span>
                      {player.is_bot && <span className="text-purple-600 text-xs">Bot</span>}
                      {player.id === playerId && <span className="bg-blue-500 text-white px-2 py-1 rounded text-xs">You</span>}
                    </div>
                  </div>
                ))}
              </div>
              {spectators.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-xs font-semibold text-gray-600 mb-2">Spectators ({spectators.length})</h4>
                  <div className="space-y-1">
                    {spectators.map((player) => (
                      <div key={player.id} className={`flex items-center justify-between p-2 rounded-lg text-xs ${player.id === playerId ? "bg-purple-200" : "bg-gray-100"}`}>
                        <span className="font-medium truncate flex-1">{player.name}</span>
                        {player.id === playerId && <span className="bg-purple-500 text-white px-2 py-1 rounded text-xs">You</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-6">
              <div className="bg-gray-50 rounded-lg p-4 sm:p-6">
                <h3 className="text-base sm:text-lg font-bold mb-4 text-gray-700">Game Settings</h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-sm">Mordred</h4>
                      <p className="text-xs text-gray-600">Evil, hidden from Merlin (9+ players)</p>
                    </div>
                    <button onClick={toggleMordred}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${session.mordred_enabled ? "bg-red-500 hover:bg-red-600 text-white" : "bg-gray-300 hover:bg-gray-400 text-gray-700"}`}>
                      {session.mordred_enabled ? "On" : "Off"}
                    </button>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-sm">Oberon</h4>
                      <p className="text-xs text-gray-600">Evil, hidden from everyone (7+ players)</p>
                    </div>
                    <button onClick={toggleOberon}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${session.oberon_enabled ? "bg-red-500 hover:bg-red-600 text-white" : "bg-gray-300 hover:bg-gray-400 text-gray-700"}`}>
                      {session.oberon_enabled ? "On" : "Off"}
                    </button>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-sm">Lady of the Lake</h4>
                      <p className="text-xs text-gray-600">Reveal allegiances (7+ players)</p>
                    </div>
                    <button onClick={toggleLady}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${session.lady_of_the_lake_enabled ? "bg-yellow-500 hover:bg-yellow-600 text-white" : "bg-gray-300 hover:bg-gray-400 text-gray-700"}`}>
                      {session.lady_of_the_lake_enabled ? "On" : "Off"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 text-center">
            {canStart && !currentPlayer?.is_spectator ? (
              <div className="space-y-4">
                <button onClick={startGame} className="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-6 rounded-lg text-base sm:text-lg transition-colors w-full sm:w-auto min-h-[48px]">
                  Start Game
                </button>
                <div>
                  <button onClick={startTestGame} className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 sm:px-6 rounded-lg transition-colors w-full sm:w-auto">
                    Start Test Game (adds bots)
                  </button>
                </div>
              </div>
            ) : currentPlayer?.is_spectator ? (
              <p className="text-gray-600">You are spectating. Waiting for players to start...</p>
            ) : (
              <div className="space-y-4">
                <p className="text-gray-600">Need at least 5 players ({5 - activePlayers.length} more needed)</p>
                <button onClick={startTestGame} className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition-colors w-full sm:w-auto min-h-[48px]">
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
