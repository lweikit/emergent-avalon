import api from "../../api";
import { PhaseProps } from "./types";

export default function MissionVoting({ session, currentMission, currentPlayer, playerId, playerToken, execute, loading }: PhaseProps) {
  if (!currentMission) return null;

  const hasVoted = (pid: string, votes: Record<string, boolean> | null | undefined): boolean =>
    votes != null && Object.prototype.hasOwnProperty.call(votes, pid);

  return (
    <div>
      <p className="mb-4 text-gray-300"><span className="font-bold text-blue-400">Proposed Team:</span> {currentMission.team_members.map((id) => session.players.find((p) => p.id === id)?.name).filter(Boolean).join(", ")}</p>
      <div className="mb-4">
        <h4 className="font-semibold mb-2 text-gray-300">Votes:</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {session.players.filter((p) => !p.is_spectator).map((player) => (
            <div key={player.id} className={`p-2 rounded border text-sm ${hasVoted(player.id, currentMission.votes) ? "bg-blue-900/40 border-blue-500 text-blue-300" : "bg-gray-700 border-gray-600 text-gray-300"}`}>
              <span className="font-medium">{player.name}</span>
              {hasVoted(player.id, currentMission.votes) && <span className="ml-2 text-xs">Voted</span>}
            </div>
          ))}
        </div>
      </div>
      {!hasVoted(playerId, currentMission.votes) && !currentPlayer.is_spectator && (
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button onClick={() => execute(() => api.voteTeam(session.id, playerId, playerToken, true))}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-bold py-3 px-6 rounded-lg transition-colors min-h-[48px]">
            Approve
          </button>
          <button onClick={() => execute(() => api.voteTeam(session.id, playerId, playerToken, false))}
            disabled={loading}
            className="bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white font-bold py-3 px-6 rounded-lg transition-colors min-h-[48px]">
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
