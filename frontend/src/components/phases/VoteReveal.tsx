import { PhaseProps } from "./types";

export default function VoteReveal({ session, currentMission }: PhaseProps) {
  if (!currentMission) return null;

  return (
    <div>
      <p className="mb-4 text-gray-300"><span className="font-bold text-blue-400">Proposed Team:</span> {currentMission.team_members.map((id) => session.players.find((p) => p.id === id)?.name).filter(Boolean).join(", ")}</p>
      <div className="mb-4">
        <h4 className="font-semibold mb-2 text-gray-300">Vote Results:</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {session.players.filter((p) => !p.is_spectator).map((player) => {
            const vote = currentMission.votes?.[player.id];
            return (
              <div key={player.id} className={`p-2 rounded border text-sm font-medium ${vote ? "bg-green-900/40 border-green-500 text-green-300" : "bg-red-900/40 border-red-500 text-red-300"}`}>
                {player.name}: {vote ? "Approve" : "Reject"}
              </div>
            );
          })}
        </div>
      </div>
      <div className="text-center">
        <p className={`text-lg font-bold ${currentMission.team_approved ? "text-green-400" : "text-red-400"}`}>
          Team {currentMission.team_approved ? "APPROVED" : "REJECTED"}
        </p>
        <p className="text-xs text-gray-500 mt-2">Advancing in a few seconds...</p>
      </div>
    </div>
  );
}
