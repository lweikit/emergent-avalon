import { GOOD_ROLES } from "../../types";
import { PhaseProps } from "./types";

export default function GameEnd({ session }: PhaseProps) {

  return (
    <div className="text-center">
      <p className="text-2xl font-bold mb-2">
        {session.game_result === "good" ? <span className="text-blue-400">GOOD WINS!</span> : session.game_result === "evil" ? <span className="text-red-400">EVIL WINS!</span> : <span className="text-gray-400">GAME ENDED</span>}
      </p>
      {session.game_log.length > 0 && (
        <p className="text-sm text-gray-400 mb-4">{session.game_log[session.game_log.length - 1]}</p>
      )}
      <div className="mt-4">
        <h3 className="font-semibold mb-2 text-sm text-gray-300">Player Roles:</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {session.players.filter((p) => !p.is_spectator).map((player) => (
            <div key={player.id} className={`p-2 rounded border text-sm ${GOOD_ROLES.includes(player.role || "") ? "bg-blue-900/40 border-blue-500 text-blue-300" : "bg-red-900/40 border-red-500 text-red-300"}`}>
              <span className="font-medium">{player.name}</span>
              <span className="ml-2 text-xs">({player.role?.replace("_", " ") || "Unknown"})</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
