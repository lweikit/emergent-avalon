import { useEffect, useRef } from "react";
import { GameState, GamePhase, GOOD_ROLES, Mission, Player } from "../types";

interface SpectatorBoardProps {
  gameState: GameState;
  isConnected: boolean;
  onLeave: () => void;
}

const PHASE_LABELS: Record<string, string> = {
  lobby: "LOBBY",
  role_assignment: "ASSIGNING ROLES",
  mission_team_selection: "TEAM SELECTION",
  mission_voting: "TEAM VOTE",
  vote_reveal: "VOTE REVEAL",
  mission_execution: "MISSION IN PROGRESS",
  mission_reveal: "MISSION RESULT",
  lady_of_the_lake: "LADY OF THE LAKE",
  assassination: "ASSASSINATION",
  game_end: "GAME OVER",
};

const PHASE_COLORS: Record<string, string> = {
  lobby: "text-gray-300",
  mission_team_selection: "text-yellow-400",
  mission_voting: "text-blue-400",
  vote_reveal: "text-purple-400",
  mission_execution: "text-orange-400",
  mission_reveal: "text-cyan-400",
  lady_of_the_lake: "text-yellow-300",
  assassination: "text-red-400",
  game_end: "text-white",
};

function MissionCard({ mission, isCurrent }: { mission: Mission; isCurrent: boolean }) {
  const bg =
    mission.result === "success"
      ? "bg-green-600 border-green-500 shadow-green-500/40"
      : mission.result === "fail"
      ? "bg-red-600 border-red-500 shadow-red-500/40"
      : isCurrent
      ? "bg-amber-100 border-yellow-400 shadow-yellow-400/30"
      : "bg-stone-200/80 border-stone-400";

  const textColor = mission.result !== "pending" ? "text-white" : "text-stone-800";

  return (
    <div className="flex flex-col items-center gap-1.5">
      <span className="text-[10px] sm:text-xs text-gray-400 font-semibold uppercase tracking-wider">
        Quest {mission.number}
      </span>
      {mission.fails_required > 1 && (
        <span className="text-[9px] sm:text-[10px] text-red-400 font-bold -mt-1">Two fails required</span>
      )}
      <div className={`relative w-16 h-16 sm:w-20 sm:h-20 rounded-full flex items-center justify-center shadow-xl ${bg} ${isCurrent && mission.result === "pending" ? "ring-2 ring-yellow-400 ring-offset-2 ring-offset-gray-900" : ""}`}
        style={{ borderWidth: "3px" }}>
        <span className={`text-2xl sm:text-3xl font-black ${textColor}`}>{mission.team_size}</span>
      </div>
      {mission.result !== "pending" && (
        <span className={`text-xs font-bold uppercase ${mission.result === "success" ? "text-green-400" : "text-red-400"}`}>
          {mission.result}
        </span>
      )}
    </div>
  );
}

function VoteTrackDot({ index, filled, danger }: { index: number; filled: boolean; danger: boolean }) {
  const isFifth = index === 4;
  return (
    <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-full border-2 flex items-center justify-center transition-all ${
      filled
        ? danger
          ? "bg-red-600 border-red-400 animate-pulse shadow-lg shadow-red-500/40"
          : "bg-yellow-600 border-yellow-400 shadow-lg shadow-yellow-500/30"
        : isFifth
        ? "bg-gray-800 border-red-500/50"
        : "bg-gray-800 border-gray-600"
    }`}>
      <span className={`text-sm sm:text-base font-black ${filled ? "text-white" : isFifth ? "text-red-400/60" : "text-gray-500"}`}>
        {index + 1}
      </span>
    </div>
  );
}

function PlayerCard({
  player,
  isOnTeam,
  isGameEnd,
}: {
  player: Player;
  isOnTeam: boolean;
  isGameEnd: boolean;
}) {
  const roleColor = player.role
    ? GOOD_ROLES.includes(player.role) ? "text-blue-400" : "text-red-400"
    : "";

  return (
    <div className={`flex items-center justify-between px-4 py-3 rounded-lg border-2 transition-all ${
      isOnTeam
        ? "bg-yellow-900/40 border-yellow-500"
        : "bg-gray-800/60 border-gray-700"
    }`}>
      <div className="flex items-center gap-3 min-w-0">
        <span className={`text-lg font-bold truncate ${!player.is_connected ? "text-gray-500" : "text-white"}`}>
          {player.name}
        </span>
        {player.is_bot && <span className="text-xs bg-purple-600 text-white px-2 py-0.5 rounded">BOT</span>}
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {player.is_leader && <span className="text-yellow-400 text-lg" title="Leader">&#9813;</span>}
        {player.lady_of_the_lake && <span className="text-cyan-400 text-lg" title="Lady of the Lake">&#9734;</span>}
        {isOnTeam && <span className="text-xs bg-yellow-600 text-white px-2 py-0.5 rounded font-bold">TEAM</span>}
        {isGameEnd && player.role && (
          <span className={`text-sm font-bold ${roleColor}`}>
            {player.role.replace("_", " ").toUpperCase()}
          </span>
        )}
        <span className={`w-2.5 h-2.5 rounded-full ${player.is_connected ? "bg-green-500" : "bg-red-500"}`} />
      </div>
    </div>
  );
}

function PhaseDisplay({ session, players }: { session: GameState["session"]; players: Player[] }) {
  const phase = session.phase;
  const currentMission = session.current_mission < session.missions.length
    ? session.missions[session.current_mission]
    : null;
  const leader = players.find((p) => p.is_leader);
  const teamNames = currentMission?.team_members
    .map((id) => players.find((p) => p.id === id)?.name)
    .filter(Boolean)
    .join(", ");

  if (phase === GamePhase.LOBBY) {
    const active = players.filter((p) => !p.is_spectator);
    return (
      <div className="text-center">
        <p className="text-2xl text-gray-300">Waiting for players...</p>
        <p className="text-lg text-gray-500 mt-2">{active.length} player{active.length !== 1 ? "s" : ""} in lobby</p>
      </div>
    );
  }

  if (phase === GamePhase.MISSION_TEAM_SELECTION) {
    return (
      <div className="text-center">
        <p className="text-xl text-gray-300">
          <span className="text-yellow-400 font-bold">{leader?.name}</span> is selecting a team of{" "}
          <span className="text-yellow-400 font-bold">{currentMission?.team_size}</span>
        </p>
        {teamNames && <p className="text-lg text-gray-400 mt-3">Proposed: {teamNames}</p>}
      </div>
    );
  }

  if (phase === GamePhase.MISSION_VOTING && currentMission) {
    return (
      <div className="text-center">
        <p className="text-xl text-gray-300">Voting on team: <span className="text-blue-400 font-bold">{teamNames}</span></p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <div className="w-12 h-12 rounded-full border-4 border-blue-500 border-t-transparent animate-spin" />
        </div>
        <p className="text-sm text-gray-500 mt-4">Waiting for all players to vote...</p>
      </div>
    );
  }

  if (phase === GamePhase.VOTE_REVEAL && currentMission) {
    return (
      <div className="text-center">
        <p className="text-xl text-gray-300 mb-4">Team: {teamNames}</p>
        <div className="flex flex-wrap justify-center gap-2 mb-4">
          {players.filter((p) => !p.is_spectator).map((p) => {
            const vote = currentMission.votes?.[p.id];
            return (
              <div key={p.id} className={`px-4 py-2 rounded-lg text-sm font-bold ${vote ? "bg-green-600 text-white" : "bg-red-600 text-white"}`}>
                {p.name}: {vote ? "APPROVE" : "REJECT"}
              </div>
            );
          })}
        </div>
        <p className={`text-2xl font-black ${currentMission.team_approved ? "text-green-400" : "text-red-400"}`}>
          Team {currentMission.team_approved ? "APPROVED" : "REJECTED"}
        </p>
      </div>
    );
  }

  if (phase === GamePhase.MISSION_EXECUTION && currentMission) {
    const missionVotes = currentMission.mission_votes;
    const voted = missionVotes && typeof missionVotes === "object" && "total_votes" in missionVotes
      ? missionVotes.total_votes : 0;
    return (
      <div className="text-center">
        <p className="text-xl text-gray-300">Mission Team: <span className="text-orange-400 font-bold">{teamNames}</span></p>
        <div className="mt-4 flex items-center justify-center gap-3">
          <div className="w-12 h-12 rounded-full border-4 border-orange-500 border-t-transparent animate-spin" />
        </div>
        <p className="text-sm text-gray-500 mt-3">{voted}/{currentMission.team_members.length} votes submitted</p>
      </div>
    );
  }

  if (phase === GamePhase.MISSION_REVEAL && currentMission) {
    const isSuccess = currentMission.result === "success";
    const mv = currentMission.mission_votes;
    return (
      <div className="text-center">
        <div className={`inline-block px-10 py-6 rounded-2xl text-3xl font-black shadow-2xl ${isSuccess ? "bg-green-600 text-white" : "bg-red-600 text-white"}`}>
          MISSION {isSuccess ? "SUCCESS" : "FAILED"}
        </div>
        {mv && typeof mv === "object" && "total_votes" in mv && (
          <p className="text-lg text-gray-400 mt-4">
            {mv.success_count ?? 0} success, {mv.fail_count ?? 0} fail
          </p>
        )}
      </div>
    );
  }

  if (phase === GamePhase.LADY_OF_THE_LAKE) {
    const holder = players.find((p) => p.lady_of_the_lake);
    return (
      <div className="text-center">
        <p className="text-xl text-yellow-300">
          <span className="font-bold">{holder?.name}</span> is using the Lady of the Lake
        </p>
      </div>
    );
  }

  if (phase === GamePhase.ASSASSINATION) {
    return (
      <div className="text-center">
        <p className="text-2xl text-red-400 font-bold animate-pulse">The Assassin is choosing a target...</p>
        <p className="text-lg text-gray-400 mt-2">Good completed 3 missions. Can evil find Merlin?</p>
      </div>
    );
  }

  if (phase === GamePhase.GAME_END) {
    return (
      <div className="text-center">
        <p className={`text-4xl font-black ${session.game_result === "good" ? "text-blue-400" : session.game_result === "evil" ? "text-red-400" : "text-gray-400"}`}>
          {session.game_result === "good" ? "GOOD WINS!" : session.game_result === "evil" ? "EVIL WINS!" : "GAME ENDED"}
        </p>
        {session.game_log.length > 0 && (
          <p className="text-lg text-gray-400 mt-3">{session.game_log[session.game_log.length - 1]}</p>
        )}
      </div>
    );
  }

  return null;
}

export default function SpectatorBoard({ gameState, isConnected, onLeave }: SpectatorBoardProps) {
  const session = gameState?.session;
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [session?.game_log?.length]);

  if (!session) return null;

  const activePlayers = session.players.filter((p) => !p.is_spectator);
  const currentMission = session.current_mission < session.missions.length
    ? session.missions[session.current_mission]
    : null;
  const teamMemberIds = new Set(currentMission?.team_members || []);

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-2xl font-black tracking-tight">{session.name}</h1>
            {session.code && (
              <span className="text-sm font-mono tracking-wider bg-gray-700 px-3 py-1 rounded text-gray-300">
                {session.code}
              </span>
            )}
            <span className={`text-xl font-bold ${PHASE_COLORS[session.phase] || "text-gray-300"}`}>
              {PHASE_LABELS[session.phase] || session.phase}
            </span>
          </div>
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-6 text-center">
              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wide">Good</span>
                <p className="text-3xl font-black text-blue-400">{session.good_wins}</p>
              </div>
              <span className="text-gray-600 text-2xl">:</span>
              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wide">Evil</span>
                <p className="text-3xl font-black text-red-400">{session.evil_wins}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500 animate-pulse"}`} />
              <span className="text-xs text-gray-500">{isConnected ? "LIVE" : "OFFLINE"}</span>
            </div>
            <button onClick={onLeave} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
              EXIT
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 max-w-7xl mx-auto w-full px-6 py-6 flex flex-col gap-6" style={{ minHeight: 0 }}>
        {/* Hero: Mission Track + Vote Track centered */}
        <div className="bg-gray-800 rounded-xl p-6 sm:p-8 border border-gray-700">
          {session.missions.length > 0 && (
            <div className="flex gap-6 sm:gap-10 justify-center items-end mb-8">
              {session.missions.map((m, i) => (
                <MissionCard key={i} mission={m} isCurrent={i === session.current_mission} />
              ))}
            </div>
          )}
          <div className="flex items-center justify-center gap-6">
            <span className="text-xs text-gray-500 uppercase tracking-wider font-bold">Vote Track</span>
            <div className="flex gap-2 sm:gap-3">
              {[0, 1, 2, 3, 4].map((i) => (
                <VoteTrackDot key={i} index={i} filled={i < session.vote_track} danger={session.vote_track >= 4} />
              ))}
            </div>
            {session.vote_track >= 4 && <span className="text-red-400 text-xs animate-pulse font-bold">DANGER</span>}
          </div>
        </div>

        {/* Phase display centered */}
        <div className="bg-gray-800 rounded-xl p-8 border border-gray-700 flex items-center justify-center min-h-[160px]">
          <PhaseDisplay session={session} players={activePlayers} />
        </div>

        {/* Bottom row: Vote History + Game Log + Players */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
          {/* Vote History */}
          <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 flex flex-col">
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wide mb-3">Vote History</h2>
            {session.vote_history && session.vote_history.length > 0 ? (
              <div className="overflow-y-auto flex-1 space-y-2">
                {session.vote_history.map((vote, i) => (
                  <div key={i} className="bg-gray-900 rounded-lg p-3">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-xs font-bold text-gray-400">Mission {vote.mission}</span>
                      <span className={`text-xs font-bold ${vote.result === "approved" ? "text-green-400" : "text-red-400"}`}>
                        {vote.result.toUpperCase()}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(vote.votes).map(([name, v]) => (
                        <span key={name} className={`text-xs px-1.5 py-0.5 rounded ${v ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"}`}>
                          {name}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-600 italic">No votes yet</p>
            )}
          </div>

          {/* Game Log */}
          <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 flex flex-col">
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wide mb-3">Game Log</h2>
            <div ref={logRef} className="overflow-y-auto flex-1 space-y-1">
              {session.game_log && session.game_log.length > 0 ? (
                session.game_log.map((log, i) => (
                  <p key={i} className="text-sm text-gray-400 font-mono">{log}</p>
                ))
              ) : (
                <p className="text-sm text-gray-600 italic">No events yet</p>
              )}
            </div>
          </div>

          {/* Players */}
          <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 flex flex-col">
            <h2 className="text-sm font-bold text-gray-500 uppercase tracking-wide mb-4">
              Players ({activePlayers.length})
            </h2>
            <div className="space-y-2 flex-1 overflow-y-auto">
              {activePlayers.map((player) => (
                <PlayerCard
                  key={player.id}
                  player={player}
                  isOnTeam={teamMemberIds.has(player.id)}
                  isGameEnd={session.phase === GamePhase.GAME_END}
                />
              ))}
            </div>
            {session.players.filter((p) => p.is_spectator).length > 0 && (
              <div className="mt-4 pt-3 border-t border-gray-700">
                <h3 className="text-xs text-gray-600 uppercase mb-2">Spectators</h3>
                <div className="flex flex-wrap gap-2">
                  {session.players.filter((p) => p.is_spectator).map((p) => (
                    <span key={p.id} className="text-xs text-gray-500 bg-gray-900 px-2 py-1 rounded">{p.name}</span>
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
