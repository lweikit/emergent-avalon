import { useState, useEffect, useRef } from "react";
import api from "../api";
import { GameState, GamePhase } from "../types";
import useAsyncAction from "../hooks/useAsyncAction";
import { TeamSelection, MissionVoting, VoteReveal, MissionExecution, MissionReveal, LadyOfTheLake, Assassination, GameEnd } from "./phases";
import RuleBook from "./RuleBook";

interface GameBoardProps {
  gameState: GameState;
  playerId: string | null;
  playerToken: string | null;
  isConnected: boolean;
  onLeave: () => void;
}

export default function GameBoard({ gameState, playerId, playerToken, isConnected, onLeave }: GameBoardProps) {
  const session = gameState?.session;
  const currentMission = gameState?.current_mission_details;
  const roleInfo = gameState?.role_info;
  const currentPlayer = session?.players?.find((p) => p.id === playerId);
  const currentLeader = session?.players?.find((p) => p.is_leader);

  const [selectedTeam, setSelectedTeam] = useState<string[]>([]);
  const [showEndGameConfirm, setShowEndGameConfirm] = useState(false);
  const [showVoteHistory, setShowVoteHistory] = useState(false);
  const [showGameLog, setShowGameLog] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const { execute, loading, error } = useAsyncAction();

  useEffect(() => { setSelectedTeam([]); }, [session?.current_mission]);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [session?.game_log?.length]);

  if (!session || !currentPlayer || !playerId || !playerToken) return null;

  const displayCode = session.code || session.id.slice(0, 8);

  const phaseProps = {
    session, currentMission: currentMission ?? null, currentPlayer, currentLeader,
    playerId, playerToken, roleInfo, selectedTeam, setSelectedTeam, execute, loading,
  };

  const phaseComponent = (() => {
    switch (session.phase) {
      case GamePhase.MISSION_TEAM_SELECTION: return <TeamSelection {...phaseProps} />;
      case GamePhase.MISSION_VOTING: return <MissionVoting {...phaseProps} />;
      case GamePhase.VOTE_REVEAL: return <VoteReveal {...phaseProps} />;
      case GamePhase.MISSION_EXECUTION: return <MissionExecution {...phaseProps} />;
      case GamePhase.MISSION_REVEAL: return <MissionReveal {...phaseProps} />;
      case GamePhase.LADY_OF_THE_LAKE: return <LadyOfTheLake {...phaseProps} />;
      case GamePhase.ASSASSINATION: return <Assassination {...phaseProps} />;
      case GamePhase.GAME_END: return <GameEnd {...phaseProps} />;
      default: return null;
    }
  })();

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4">
      <div className="max-w-6xl mx-auto px-4">
        {/* Header */}
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 sm:p-6 mb-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex-1 min-w-0">
              <h1 className="text-lg sm:text-xl md:text-2xl font-bold text-white truncate">{session.name}</h1>
              <p className="text-xs sm:text-sm text-gray-400">Phase: {session.phase.replace(/_/g, " ").toUpperCase()}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <button onClick={() => navigator.clipboard.writeText(displayCode)}
                  className="bg-gray-700 hover:bg-gray-600 text-gray-300 px-3 py-2 rounded transition-colors min-h-[44px] font-mono tracking-wider">
                  Room: {displayCode}
                </button>
                <div className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500 animate-pulse"}`} />
                  <span className="text-gray-400">{isConnected ? "LIVE" : "OFFLINE"}</span>
                </div>
                <button onClick={onLeave} className="text-gray-500 hover:text-gray-300 px-3 py-2 rounded transition-colors text-xs min-h-[44px]">
                  Leave
                </button>
              </div>
            </div>
            <div className="flex gap-4 text-center">
              <div><p className="text-xs text-gray-500">Good</p><p className="text-lg font-bold text-blue-400">{session.good_wins}</p></div>
              <div><p className="text-xs text-gray-500">Evil</p><p className="text-lg font-bold text-red-400">{session.evil_wins}</p></div>
              <div><p className="text-xs text-gray-500">Votes</p><p className={`text-lg font-bold ${session.vote_track >= 4 ? "text-red-400 animate-pulse" : "text-yellow-400"}`}>{session.vote_track}/5</p></div>
            </div>
          </div>
          {error && <div className="mt-3 p-2 bg-red-900/40 border border-red-500 text-red-300 rounded text-xs">{error}</div>}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
          {/* Main panel */}
          <div className="lg:col-span-2 space-y-4 sm:space-y-6 order-2 lg:order-1">
            {/* Role info */}
            {roleInfo && (
              <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 sm:p-6">
                <h2 className="text-base sm:text-lg font-bold mb-4 text-white">Your Role: {roleInfo.role.replace("_", " ").toUpperCase()}</h2>
                <div className={`p-4 rounded-lg ${roleInfo.team === "good" ? "bg-blue-900/30 border-l-4 border-blue-500" : "bg-red-900/30 border-l-4 border-red-500"}`}>
                  <p className="font-medium mb-2 text-sm text-gray-300">Team: <span className={roleInfo.team === "good" ? "text-blue-400" : "text-red-400"}>{roleInfo.team.toUpperCase()}</span></p>
                  <p className="text-sm text-gray-400 mb-3">{roleInfo.description}</p>
                  {roleInfo.sees?.length > 0 && (
                    <div>
                      <p className="font-medium text-sm mb-2 text-gray-300">You can see:</p>
                      <div className="flex flex-wrap gap-2">
                        {roleInfo.sees.map((s, i) => <span key={i} className="bg-gray-700 px-2 py-1 rounded text-xs text-gray-300">{s.name} ({s.role})</span>)}
                      </div>
                    </div>
                  )}
                </div>
                {gameState?.lady_of_lake_knowledge && gameState.lady_of_lake_knowledge.length > 0 && (
                  <div className="mt-4 p-4 bg-yellow-900/20 border-l-4 border-yellow-500 rounded-lg">
                    <h3 className="font-bold text-yellow-300 mb-2 text-sm">Lady of the Lake Knowledge:</h3>
                    <div className="space-y-2">
                      {gameState.lady_of_lake_knowledge.map((k, i) => (
                        <span key={i} className={`inline-block px-3 py-1 rounded-lg text-sm font-medium mr-2 ${k.allegiance === "good" ? "bg-blue-600 text-white" : "bg-red-600 text-white"}`}>
                          {k.target_name}: {k.allegiance.toUpperCase()}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Missions grid */}
            <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 sm:p-6">
              <h2 className="text-lg font-bold mb-4 text-white">Missions</h2>
              <div className="flex gap-4 sm:gap-5 justify-center items-start">
                {session.missions.map((mission, index) => {
                  const isCurrent = index === session.current_mission;
                  const bg =
                    mission.result === "success" ? "bg-green-600 border-green-500"
                    : mission.result === "fail" ? "bg-red-600 border-red-500"
                    : isCurrent ? "bg-amber-100 border-yellow-400"
                    : "bg-stone-200 border-stone-400";
                  const textColor = mission.result !== "pending" ? "text-white" : "text-stone-800";
                  return (
                    <div key={index} className="flex flex-col items-center gap-1">
                      <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider">Quest {mission.number}</span>
                      {mission.fails_required > 1 && (
                        <span className="text-[9px] text-red-400 font-bold -mt-1">2 fails</span>
                      )}
                      <div className={`w-12 h-12 sm:w-14 sm:h-14 rounded-full flex items-center justify-center shadow-lg ${bg} ${isCurrent && mission.result === "pending" ? "ring-2 ring-yellow-400 ring-offset-2 ring-offset-gray-900" : ""}`}
                        style={{ borderWidth: "3px" }}>
                        <span className={`text-lg sm:text-xl font-black ${textColor}`}>{mission.team_size}</span>
                      </div>
                      {mission.result !== "pending" && (
                        <span className={`text-[10px] font-bold ${mission.result === "success" ? "text-green-400" : "text-red-400"}`}>
                          {mission.result}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Current phase action */}
            {phaseComponent && (
              <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 sm:p-6">
                <h2 className="text-lg font-bold mb-4 text-white">
                  {session.phase === GamePhase.GAME_END ? "Game Over!" : `Mission ${currentMission?.number ?? ""}`}
                </h2>
                {phaseComponent}
              </div>
            )}
          </div>

          {/* Side panel */}
          <div className="space-y-4 order-3 lg:order-2">
            {/* Players */}
            <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 sm:p-6">
              <h2 className="text-base sm:text-lg font-bold mb-4 text-white">Players</h2>
              <div className="space-y-2 mb-4">
                {session.players.filter((p) => !p.is_spectator).map((player) => (
                  <div key={player.id} className={`p-2 sm:p-3 rounded-lg border-2 text-sm ${player.id === playerId ? "bg-blue-900/30 border-blue-500" : "bg-gray-700/50 border-gray-600"}`}>
                    <div className="flex items-center justify-between">
                      <span className={`font-medium truncate flex-1 ${player.is_connected ? "text-white" : "text-gray-500"}`}>{player.name}</span>
                      <div className="flex items-center space-x-1 flex-shrink-0">
                        {player.is_leader && <span className="text-yellow-400 text-sm" title="Leader">&#9813;</span>}
                        {player.lady_of_the_lake && <span className="text-cyan-400 text-sm" title="Lady of the Lake">&#9734;</span>}
                        {player.is_bot && <span className="text-purple-400 text-xs">Bot</span>}
                        <span className={`w-2 h-2 rounded-full ${player.is_connected ? "bg-green-500" : "bg-red-500"}`} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {session.players.filter((p) => p.is_spectator).length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold text-gray-500 uppercase">Spectators</h3>
                  {session.players.filter((p) => p.is_spectator).map((player) => (
                    <div key={player.id} className={`p-2 rounded-lg border text-xs ${player.id === playerId ? "bg-purple-900/30 border-purple-500" : "bg-gray-700/50 border-gray-600"}`}>
                      <span className="text-gray-300">{player.name}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* End game modal */}
            {showEndGameConfirm && (
              <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 p-4">
                <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 max-w-md w-full">
                  <h3 className="text-lg font-bold text-white mb-4">End Game?</h3>
                  <p className="text-sm text-gray-400 mb-6">This will reveal all player roles and end the current game.</p>
                  <div className="flex gap-3">
                    <button onClick={() => setShowEndGameConfirm(false)} className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 font-bold py-3 px-4 rounded-lg min-h-[48px]">Cancel</button>
                    <button onClick={() => { api.endGame(session.id); setShowEndGameConfirm(false); }} className="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-4 rounded-lg min-h-[48px]">Yes, End</button>
                  </div>
                </div>
              </div>
            )}

            {/* Controls */}
            <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 sm:p-6">
              <h2 className="text-base font-bold mb-4 text-white">Controls</h2>
              <div className="space-y-3">
                <button onClick={() => setShowVoteHistory(!showVoteHistory)}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                  {showVoteHistory ? "Hide" : "Show"} Vote History
                </button>
                <button onClick={() => setShowGameLog(!showGameLog)}
                  className="w-full bg-gray-700 hover:bg-gray-600 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                  {showGameLog ? "Hide" : "Show"} Game Log
                </button>
                {session.phase !== GamePhase.GAME_END && (
                  <button onClick={() => setShowEndGameConfirm(true)}
                    className="w-full bg-orange-600 hover:bg-orange-700 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                    End Game & Reveal Roles
                  </button>
                )}
                {session.phase === GamePhase.GAME_END && (
                  <button onClick={() => api.restartGame(session.id)}
                    className="w-full bg-purple-600 hover:bg-purple-700 text-white font-bold py-3 px-4 rounded-lg transition-colors text-sm min-h-[48px]">
                    Restart Game
                  </button>
                )}
              </div>
            </div>

            {/* Vote history */}
            {showVoteHistory && session.vote_history?.length > 0 && (
              <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 sm:p-6">
                <h2 className="text-lg font-bold mb-4 text-white">Vote History</h2>
                <div className="space-y-3 max-h-64 overflow-y-auto">
                  {session.vote_history.map((vote, index) => (
                    <div key={index} className="p-3 bg-gray-900 rounded-lg">
                      <div className="font-semibold text-sm text-gray-300">Mission {vote.mission} - {vote.result}</div>
                      <div className="text-xs text-gray-500 mt-1">{vote.approve_count}/{vote.total_votes} approved</div>
                      <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
                        {Object.entries(vote.votes).map(([name, v]) => (
                          <div key={name} className="flex justify-between">
                            <span className="text-gray-400">{name}:</span>
                            <span className={v ? "text-green-400" : "text-red-400"}>{v ? "Yes" : "No"}</span>
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
              <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 sm:p-6">
                <h2 className="text-lg font-bold mb-4 text-white">Game Log</h2>
                <div ref={logRef} className="space-y-2 max-h-64 overflow-y-auto">
                  {session.game_log.map((log, index) => (
                    <div key={index} className="p-2 bg-gray-900 rounded text-xs sm:text-sm text-gray-400">{log}</div>
                  ))}
                </div>
              </div>
            )}
            <RuleBook />
          </div>
        </div>
      </div>
    </div>
  );
}
