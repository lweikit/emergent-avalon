import { PhaseProps } from "./types";

export default function MissionReveal({ session, currentMission }: PhaseProps) {
  if (!currentMission) return null;

  return (
    <div className="text-center space-y-4">
      <p className="mb-2 text-gray-300"><span className="font-bold">Mission Team:</span> {currentMission.team_members.map((id) => session.players.find((p) => p.id === id)?.name).filter(Boolean).join(", ")}</p>
      <div className={`inline-block px-6 py-4 rounded-xl text-xl font-bold shadow-lg ${currentMission.result === "success" ? "bg-blue-600 text-white" : "bg-red-600 text-white"}`}>
        Mission {currentMission.result === "success" ? "SUCCESS" : "FAILED"}
      </div>
      {currentMission.mission_votes && (
        <p className="text-sm text-gray-400">
          {currentMission.mission_votes.success_count ?? 0} success, {currentMission.mission_votes.fail_count ?? 0} fail
        </p>
      )}
      <p className="text-xs text-gray-500">Advancing in a few seconds...</p>
    </div>
  );
}
