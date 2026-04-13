import { useState } from "react";
import api from "../api";
import { GameState, LadyResult } from "../types";

interface GameBoardProps {
  gameState: GameState;
  playerId: string | null;
  playerToken: string | null;
  isConnected: boolean;
}

interface AxiosErrorResponse {
  response?: {
    data?: {
      detail?: string;
    };
  };
  message: string;
}

export default function GameBoard({ gameState, playerId, playerToken, isConnected }: GameBoardProps) {
  const session = gameState?.session;
  const currentMission = gameState?.current_mission_details;
  const roleInfo = gameState?.role_info;
  const currentPlayer = session?.players?.find((p) => p.id === playerId);
  const currentLeader = session?.players?.find((p) => p.is_leader);

  const [selectedTeam, setSelectedTeam] = useState<string[]>([]);
  const [ladyTarget, setLadyTarget] = useState<string | null>(null);
  const [assassinTarget, setAssassinTarget] = useState("");
  const [ladyResult, setLadyResult] = useState<LadyResult | null>(null);
  const [showLadyResult, setShowLadyResult] = useState(false);
  const [showEndGameConfirm, setShowEndGameConfirm] = useState(false);
  const [showVoteHistory, setShowVoteHistory] = useState(false);
  const [showGameLog, setShowGameLog] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");

  if (!session || !currentPlayer || !playerId || !playerToken) return null;

  const hasVoted = (pid: string | null, votes: Record<string, boolean> | null | undefined): boolean =>
    votes != null && pid != null && Object.prototype.hasOwnProperty.call(votes, pid);
  const isLeader = currentPlayer?.is_leader;

  const withLoading = async (fn: () => Promise<unknown>) => {
    if (actionLoading) return;
    setActionLoading(true);
    setError("");
    try { await fn(); } catch (e) {
      const err = e as AxiosErrorResponse;
      setError(err.response?.data?.detail || "Action failed");
    }
    finally { setActionLoading(false); }
  };

  const toggleTeamMember = (id: string) => {
    if (!currentMission) return;
    if (selectedTeam.includes(id)) {
      setSelectedTeam(selectedTeam.filter((x) => x !== id));
    } else if (selectedTeam.length < currentMission.team_size) {
      setSelectedTeam([...selectedTeam, id]);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 to-blue-900 p-4">
      <div className="max-w-6xl mx-auto px-4">
        {/* Header */}
        <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6 mb-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex-1 min-w-0">
              <h1 className="text-lg sm:text-xl md:text-2xl font-bold text-gray-800 truncate">{session.name}</h1>
              <p className="text-xs sm:text-sm text-gray-600">Phase: {session.phase.replace(/_/g, " ").toUpperCase()}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <button onClick={() => navigator.clipboard.writeText(session.id)}
                  className="bg-blue-100 hover:bg-blue-200 text-blue-800 px-3 py-2 rounded transition-colors min-h-[44px]">
                  ID: {session.id.slice(0, 8)}...
                </button>
                <span className={`px-2 py-1 rounded ${isConnected ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
                  {isConnected ? "Real-time" : "Offline"}
                </span>
              </div>
            </div>
            <div className="flex gap-4 text-center">
              <div><p className="text-xs text-gray-600">Good</p><p className="text-lg font-bold text-green-600">{session.good_wins}</p></div>
              <div><p className="text-xs text-gray-600">Evil</p><p className="text-lg font-bold text-red-600">{session.evil_wins}</p></div>
              <div><p className="text-xs text-gray-600">Votes</p><p className={`text-lg font-bold ${session.vote_track >= 4 ? "text-red-600 animate-pulse" : "text-yellow-600"}`}>{session.vote_track}/5</p></div>
            </div>
          </div>
          {error && <div className="mt-3 p-2 bg-red-100 border border-red-300 text-red-700 rounded text-xs">{error}</div>}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
          {/* Main panel */}
          <div className="lg:col-span-2 space-y-4 sm:space-y-6 order-2 lg:order-1">
            {/* Role info */}
            {roleInfo && (
              <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                <h2 className="text-base sm:text-lg font-bold mb-4 text-gray-800">Your Role: {roleInfo.role.replace("_", " ").toUpperCase()}</h2>
                <div className={`p-4 rounded-lg ${roleInfo.team === "good" ? "bg-blue-50 border-l-4 border-blue-500" : "bg-red-50 border-l-4 border-red-500"}`}>
                  <p className="font-medium mb-2 text-sm">Team: <span className={roleInfo.team === "good" ? "text-blue-600" : "text-red-600"}>{roleInfo.team.toUpperCase()}</span></p>
                  <p className="text-sm text-gray-700 mb-3">{roleInfo.description}</p>
                  {roleInfo.sees?.length > 0 && (
                    <div>
                      <p className="font-medium text-sm mb-2">You can see:</p>
                      <div className="flex flex-wrap gap-2">
                        {roleInfo.sees.map((s, i) => <span key={i} className="bg-gray-200 px-2 py-1 rounded text-xs">{s.name} ({s.role})</span>)}
                      </div>
                    </div>
                  )}
                </div>
                {gameState?.lady_of_lake_knowledge && gameState.lady_of_lake_knowledge.length > 0 && (
                  <div className="mt-4 p-4 bg-yellow-50 border-l-4 border-yellow-500 rounded-lg">
                    <h3 className="font-bold text-yellow-800 mb-2 text-sm">Lady of the Lake Knowledge:</h3>
                    <div className="space-y-2">
                      {gameState.lady_of_lake_knowledge.map((k, i) => (
                        <span key={i} className={`inline-block px-3 py-1 rounded-lg text-sm font-medium mr-2 ${k.allegiance === "good" ? "bg-blue-500 text-white" : "bg-red-500 text-white"}`}>
                          {k.target_name}: {k.allegiance.toUpperCase()}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Missions grid */}
            <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
              <h2 className="text-lg font-bold mb-4 text-gray-800">Missions</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 mb-4">
                {session.missions.map((mission, index) => (
                  <div key={index} className={`p-2 sm:p-3 rounded-lg text-center border-2 text-xs sm:text-sm ${
                    index === session.current_mission ? "bg-yellow-100 border-yellow-500"
                    : mission.result === "success" ? "bg-green-100 border-green-500"
                    : mission.result === "fail" ? "bg-red-100 border-red-500"
                    : "bg-gray-100 border-gray-300"
                  }`}>
                    <div className="font-bold">#{mission.number}</div>
                    <div className="text-xs">{mission.team_size} players</div>
                    <div className="text-xs">{mission.fails_required} fail{mission.fails_required > 1 ? "s" : ""}</div>
                    {mission.result !== "pending" && (
                      <div className={`text-xs font-bold ${mission.result === "success" ? "text-green-600" : "text-red-600"}`}>{mission.result.toUpperCase()}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Current mission actions */}
            {currentMission && (
              <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                <h2 className="text-lg font-bold mb-4 text-gray-800">Mission {currentMission.number}</h2>

                {/* Team selection */}
                {session.phase === "mission_team_selection" && (
                  <div>
                    <p className="mb-4"><strong>Leader:</strong> {currentLeader?.name} must select {currentMission.team_size} players</p>
                    {isLeader && (
                      <div className="space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                          {session.players.filter((p) => !p.is_spectator).map((player) => (
                            <button key={player.id} onClick={() => toggleTeamMember(player.id)}
                              className={`p-2 sm:p-3 rounded-lg border-2 transition-colors text-sm ${selectedTeam.includes(player.id) ? "bg-blue-500 text-white border-blue-500" : "bg-white border-gray-300 hover:border-blue-300"}`}>
                              {player.name}
                            </button>
                          ))}
                        </div>
                        <div className="text-center">
                          <p className="mb-2">Selected: {selectedTeam.length}/{currentMission.team_size}</p>
                          <button onClick={() => withLoading(async () => { await api.selectTeam(session.id, playerId, playerToken, selectedTeam); setSelectedTeam([]); })}
                            disabled={selectedTeam.length !== currentMission.team_size || actionLoading}
                            className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-bold py-2 px-6 rounded-lg transition-colors">
                            {actionLoading ? "Proposing..." : "Propose Team"}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Team voting */}
                {session.phase === "mission_voting" && (
                  <div>
                    <p className="mb-4"><strong>Proposed Team:</strong> {currentMission.team_members.map((id) => session.players.find((p) => p.id === id)?.name).filter(Boolean).join(", ")}</p>
                    <div className="mb-4">
                      <h4 className="font-semibold mb-2">Votes:</h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {session.players.filter((p) => !p.is_spectator).map((player) => (
                          <div key={player.id} className={`p-2 rounded border text-sm ${hasVoted(player.id, currentMission.votes) ? "bg-blue-100 border-blue-300" : "bg-gray-100 border-gray-300"}`}>
                            <span className="font-medium">{player.name}</span>
                            {hasVoted(player.id, currentMission.votes) && <span className="ml-2 text-xs">Voted</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                    {!hasVoted(playerId, currentMission.votes) && !currentPlayer.is_spectator && (
                      <div className="flex flex-col sm:flex-row gap-3 justify-center">
                        <button onClick={() => withLoading(() => api.voteTeam(session.id, playerId, playerToken, true))}
                          disabled={actionLoading}
                          className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-bold py-3 px-6 rounded-lg transition-colors min-h-[48px]">
                          Approve
                        </button>
                        <button onClick={() => withLoading(() => api.voteTeam(session.id, playerId, playerToken, false))}
                          disabled={actionLoading}
                          className="bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white font-bold py-3 px-6 rounded-lg transition-colors min-h-[48px]">
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Vote reveal */}
                {session.phase === "vote_reveal" && currentMission && (
                  <div>
                    <p className="mb-4"><strong>Proposed Team:</strong> {currentMission.team_members.map((id) => session.players.find((p) => p.id === id)?.name).filter(Boolean).join(", ")}</p>
                    <div className="mb-4">
                      <h4 className="font-semibold mb-2">Vote Results:</h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {session.players.filter((p) => !p.is_spectator).map((player) => {
                          const vote = currentMission.votes?.[player.id];
                          return (
                            <div key={player.id} className={`p-2 rounded border text-sm font-medium ${vote ? "bg-green-100 border-green-400 text-green-800" : "bg-red-100 border-red-400 text-red-800"}`}>
                              {player.name}: {vote ? "Approve" : "Reject"}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                    <div className="text-center">
                      <p className={`text-lg font-bold ${currentMission.team_approved ? "text-green-600" : "text-red-600"}`}>
                        Team {currentMission.team_approved ? "APPROVED" : "REJECTED"}
                      </p>
                      <p className="text-xs text-gray-500 mt-2">Advancing in a few seconds...</p>
                    </div>
                  </div>
                )}

                {/* Mission execution */}
                {session.phase === "mission_execution" && (
                  <div>
                    <p className="mb-4"><strong>Mission Team:</strong> {currentMission.team_members.map((id) => session.players.find((p) => p.id === id)?.name).filter(Boolean).join(", ")}</p>
                    {currentMission.team_members.includes(playerId) && !currentMission.mission_votes?.player_voted && (
                      <div>
                        <p className="mb-4 font-semibold">You are on this mission! Choose your action:</p>
                        <div className="flex flex-col sm:flex-row gap-3 justify-center">
                          <button onClick={() => withLoading(() => api.voteMission(session.id, playerId, playerToken, true))}
                            disabled={actionLoading}
                            className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-bold py-3 px-6 rounded-lg transition-colors min-h-[48px]">
                            Success
                          </button>
                          {roleInfo?.team === "evil" && (
                            <button onClick={() => withLoading(() => api.voteMission(session.id, playerId, playerToken, false))}
                              disabled={actionLoading}
                              className="bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white font-bold py-3 px-6 rounded-lg transition-colors min-h-[48px]">
                              Fail
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                    {currentMission.mission_votes && currentMission.mission_votes.total_votes > 0 && (
                      <div className="mt-4 bg-gray-100 p-3 rounded-lg">
                        <p className="text-sm text-gray-700">{currentMission.mission_votes.total_votes} of {currentMission.team_members.length} team members have voted</p>
                      </div>
                    )}
                  </div>
                )}

                {/* Mission result reveal */}
                {session.phase === "mission_reveal" && currentMission && (
                  <div className="text-center space-y-4">
                    <p className="mb-2"><strong>Mission Team:</strong> {currentMission.team_members.map((id) => session.players.find((p) => p.id === id)?.name).filter(Boolean).join(", ")}</p>
                    <div className={`inline-block px-6 py-4 rounded-xl text-xl font-bold shadow-lg ${currentMission.result === "success" ? "bg-green-500 text-white" : "bg-red-500 text-white"}`}>
                      Mission {currentMission.result === "success" ? "SUCCESS" : "FAILED"}
                    </div>
                    {currentMission.mission_votes && (
                      <p className="text-sm text-gray-600">
                        {currentMission.mission_votes.success_count ?? 0} success, {currentMission.mission_votes.fail_count ?? 0} fail
                      </p>
                    )}
                    <p className="text-xs text-gray-500">Advancing in a few seconds...</p>
                  </div>
                )}
              </div>
            )}

            {/* Lady of the Lake */}
            {session.phase === "lady_of_the_lake" && (
              <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                <h2 className="text-lg font-bold mb-4 text-gray-800">Lady of the Lake</h2>
                {currentPlayer.lady_of_the_lake && (
                  <div className="space-y-4">
                    <p className="font-semibold">Choose a player to reveal their allegiance:</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                      {session.players
                        .filter((p) => p.id !== playerId && !p.is_spectator && !(session.lady_of_the_lake_previous_holders || []).includes(p.id))
                        .map((player) => (
                        <button key={player.id} onClick={() => setLadyTarget(player.id)}
                          className={`p-2 sm:p-3 rounded-lg border-2 transition-colors text-sm ${ladyTarget === player.id ? "bg-yellow-500 text-white border-yellow-500" : "bg-white border-gray-300 hover:border-yellow-300"}`}>
                          {player.name}
                        </button>
                      ))}
                    </div>
                    {ladyTarget && (
                      <div className="text-center">
                        <button onClick={() => withLoading(async () => {
                          const res = await api.ladyOfLake(session.id, playerId, playerToken, ladyTarget);
                          setLadyResult(res.data);
                          setShowLadyResult(true);
                          setLadyTarget(null);
                          setTimeout(() => setShowLadyResult(false), 10000);
                        })}
                          disabled={actionLoading}
                          className="bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-400 text-white font-bold py-2 px-6 rounded-lg transition-colors">
                          {actionLoading ? "Revealing..." : "Use Lady of the Lake"}
                        </button>
                      </div>
                    )}
                  </div>
                )}
                {ladyResult && showLadyResult && (
                  <div className="mt-4 p-4 bg-gradient-to-r from-yellow-50 to-yellow-100 border-2 border-yellow-300 rounded-lg shadow-lg text-center">
                    <h4 className="text-lg font-bold text-yellow-800 mb-2">Lady of the Lake Reveals:</h4>
                    <div className={`inline-block px-4 py-2 rounded-lg font-bold text-lg shadow-md ${ladyResult.allegiance === "good" ? "bg-blue-500 text-white" : "bg-red-500 text-white"}`}>
                      {ladyResult.target_name} is {ladyResult.allegiance.toUpperCase()}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Assassination */}
            {session.phase === "assassination" && (
              <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                <h2 className="text-lg font-bold mb-4 text-gray-800">Assassination</h2>
                {roleInfo?.role === "assassin" ? (
                  <div className="space-y-4">
                    <p className="font-semibold text-red-600">Good has won the missions, but you can assassinate Merlin!</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                      {session.players.filter((p) => p.id !== playerId && !p.is_spectator).map((player) => (
                        <button key={player.id} onClick={() => setAssassinTarget(player.id)}
                          className={`p-2 sm:p-3 rounded-lg border-2 transition-colors text-sm ${assassinTarget === player.id ? "bg-red-500 text-white border-red-500" : "bg-white border-gray-300 hover:border-red-300"}`}>
                          {player.name}
                        </button>
                      ))}
                    </div>
                    {assassinTarget && (
                      <div className="text-center">
                        <button onClick={() => withLoading(async () => { await api.assassinate(session.id, playerId, playerToken, assassinTarget); setAssassinTarget(""); })}
                          disabled={actionLoading}
                          className="bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white font-bold py-2 px-6 rounded-lg transition-colors">
                          {actionLoading ? "Assassinating..." : `Assassinate ${session.players.find((p) => p.id === assassinTarget)?.name}`}
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-center text-sm text-gray-600">The Assassin is choosing their target...</p>
                )}
              </div>
            )}

            {/* Game end */}
            {session.phase === "game_end" && (
              <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                <h2 className="text-lg font-bold mb-4 text-gray-800">Game Over!</h2>
                <div className="text-center">
                  <p className="text-2xl font-bold mb-2">
                    {session.game_result === "good" ? <span className="text-blue-600">GOOD WINS!</span> : session.game_result === "evil" ? <span className="text-red-600">EVIL WINS!</span> : <span className="text-gray-600">GAME ENDED</span>}
                  </p>
                  {session.game_log.length > 0 && (
                    <p className="text-sm text-gray-600 mb-4">{session.game_log[session.game_log.length - 1]}</p>
                  )}
                  <div className="mt-4">
                    <h3 className="font-semibold mb-2 text-sm">Player Roles:</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {session.players.filter((p) => !p.is_spectator).map((player) => (
                        <div key={player.id} className={`p-2 rounded border text-sm ${["merlin", "percival", "loyal_servant"].includes(player.role || "") ? "bg-blue-100 border-blue-300" : "bg-red-100 border-red-300"}`}>
                          <span className="font-medium">{player.name}</span>
                          <span className="ml-2 text-xs">({player.role?.replace("_", " ") || "Unknown"})</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Side panel */}
          <div className="space-y-4 order-3 lg:order-2">
            {/* Players */}
            <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
              <h2 className="text-base sm:text-lg font-bold mb-4 text-gray-800">Players</h2>
              <div className="space-y-2 mb-4">
                {session.players.filter((p) => !p.is_spectator).map((player) => (
                  <div key={player.id} className={`p-2 sm:p-3 rounded-lg border-2 text-sm ${player.id === playerId ? "bg-blue-100 border-blue-300" : "bg-gray-50 border-gray-200"}`}>
                    <div className="flex items-center justify-between">
                      <span className="font-medium truncate flex-1">{player.name}</span>
                      <div className="flex items-center space-x-1 flex-shrink-0">
                        {player.is_leader && <span className="text-yellow-600 text-sm" title="Leader">Crown</span>}
                        {player.lady_of_the_lake && <span className="text-yellow-600 text-sm" title="Lady of the Lake">Star</span>}
                        {player.is_bot && <span className="text-purple-600 text-xs">Bot</span>}
                        <span className={`text-xs ${player.is_connected ? "text-green-600" : "text-red-600"}`}>
                          {player.is_connected ? "On" : "Off"}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {session.players.filter((p) => p.is_spectator).length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold text-gray-600 uppercase">Spectators</h3>
                  {session.players.filter((p) => p.is_spectator).map((player) => (
                    <div key={player.id} className={`p-2 rounded-lg border text-xs ${player.id === playerId ? "bg-purple-100 border-purple-300" : "bg-gray-50 border-gray-200"}`}>
                      {player.name}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* End game modal */}
            {showEndGameConfirm && (
              <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full">
                  <h3 className="text-lg font-bold text-gray-800 mb-4">End Game?</h3>
                  <p className="text-sm text-gray-600 mb-6">This will reveal all player roles and end the current game.</p>
                  <div className="flex gap-3">
                    <button onClick={() => setShowEndGameConfirm(false)} className="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-700 font-bold py-3 px-4 rounded-lg min-h-[48px]">Cancel</button>
                    <button onClick={() => { api.endGame(session.id); setShowEndGameConfirm(false); }} className="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded-lg min-h-[48px]">Yes, End</button>
                  </div>
                </div>
              </div>
            )}

            {/* Controls */}
            <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
              <h2 className="text-base font-bold mb-4 text-gray-800">Controls</h2>
              <div className="space-y-3">
                <button onClick={() => setShowVoteHistory(!showVoteHistory)}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                  {showVoteHistory ? "Hide" : "Show"} Vote History
                </button>
                <button onClick={() => setShowGameLog(!showGameLog)}
                  className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                  {showGameLog ? "Hide" : "Show"} Game Log
                </button>
                {session.phase !== "game_end" && (
                  <button onClick={() => setShowEndGameConfirm(true)}
                    className="w-full bg-orange-600 hover:bg-orange-700 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                    End Game & Reveal Roles
                  </button>
                )}
                {session.phase === "game_end" && (
                  <button onClick={() => api.restartGame(session.id)}
                    className="w-full bg-purple-600 hover:bg-purple-700 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                    Restart Game
                  </button>
                )}
              </div>
            </div>

            {/* Vote history */}
            {showVoteHistory && session.vote_history?.length > 0 && (
              <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                <h2 className="text-lg font-bold mb-4 text-gray-800">Vote History</h2>
                <div className="space-y-3 max-h-64 overflow-y-auto">
                  {session.vote_history.map((vote, index) => (
                    <div key={index} className="p-3 bg-gray-50 rounded-lg">
                      <div className="font-semibold text-sm">Mission {vote.mission} - {vote.result}</div>
                      <div className="text-xs text-gray-600 mt-1">{vote.approve_count}/{vote.total_votes} approved</div>
                      <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
                        {Object.entries(vote.votes).map(([name, v]) => (
                          <div key={name} className="flex justify-between">
                            <span>{name}:</span>
                            <span className={v ? "text-green-600" : "text-red-600"}>{v ? "Yes" : "No"}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Game log */}
            {showGameLog && session.game_log?.length > 0 && (
              <div className="bg-white rounded-xl shadow-2xl p-4 sm:p-6">
                <h2 className="text-lg font-bold mb-4 text-gray-800">Game Log</h2>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {session.game_log.map((log, index) => (
                    <div key={index} className="p-2 bg-gray-50 rounded text-xs sm:text-sm">{log}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
