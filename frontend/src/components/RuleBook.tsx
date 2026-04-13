import { useState } from "react";

const ROLES = [
  { name: "Merlin", team: "good", desc: "Knows all evil players except Mordred. Must stay hidden — if evil loses, the Assassin can still win by identifying Merlin." },
  { name: "Percival", team: "good", desc: "Sees two players: one is Merlin, one is Morgana. Doesn't know which is which. Must protect the real Merlin." },
  { name: "Loyal Servant", team: "good", desc: "No special knowledge. Relies on discussion, voting patterns, and trust to identify evil players." },
  { name: "Assassin", team: "evil", desc: "Knows other evil players (except Oberon). If good completes 3 missions, gets one chance to kill Merlin and steal the win." },
  { name: "Morgana", team: "evil", desc: "Appears as Merlin to Percival. Creates confusion about who the real Merlin is." },
  { name: "Mordred", team: "evil", desc: "Hidden from Merlin. The only evil player Merlin cannot see. Optional — toggle in lobby settings." },
  { name: "Oberon", team: "evil", desc: "Hidden from ALL other evil players, and they're hidden from Oberon. A lone wolf who must figure out allies alone. Optional — toggle in lobby settings." },
  { name: "Minion", team: "evil", desc: "Knows other evil players (except Oberon). Works with the team to sabotage missions." },
];

const RULES = [
  { title: "Goal", text: "Good team: complete 3 of 5 missions. Evil team: fail 3 missions, or get 5 team proposals rejected in a row." },
  { title: "Team Proposal", text: "The leader proposes a team of the required size. All players vote Approve or Reject. Majority approves (ties reject). If rejected, leadership passes clockwise and the vote track advances." },
  { title: "Vote Track", text: "If 5 proposals are rejected in a row, evil wins immediately. The counter resets after a mission completes." },
  { title: "Mission", text: "Approved team members secretly vote Success or Fail. Good players MUST vote Success. Evil players may vote either way. If enough Fail votes are cast (usually 1, but mission 4 with 7+ players needs 2), the mission fails." },
  { title: "Assassination", text: "If good completes 3 missions, evil gets one last chance. The Assassin picks one player they believe is Merlin. If correct, evil wins. If wrong, good wins." },
  { title: "Lady of the Lake", text: "Optional. Available with 7+ players, activates after missions 2, 3, and 4. The holder secretly views one player's allegiance (good or evil), then passes the Lady to that player. Cannot target previous holders." },
];

export default function RuleBook() {
  const [open, setOpen] = useState(false);

  return (
    <div className="w-full">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left px-4 py-3 bg-white bg-opacity-10 hover:bg-opacity-20 rounded-lg text-white text-sm font-medium transition-colors min-h-[48px] flex items-center justify-between"
      >
        <span>{open ? "Hide" : "Show"} Rules & Characters</span>
        <span className="text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="mt-2 bg-white rounded-xl shadow-2xl p-4 sm:p-6 space-y-6 text-sm">
          <div>
            <h3 className="font-bold text-gray-800 mb-3">How to Play</h3>
            <div className="space-y-2">
              {RULES.map((rule) => (
                <div key={rule.title} className="p-2 bg-gray-50 rounded">
                  <span className="font-semibold">{rule.title}:</span> {rule.text}
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="font-bold text-gray-800 mb-3">Characters</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {ROLES.map((role) => (
                <div
                  key={role.name}
                  className={`p-3 rounded border-l-4 ${role.team === "good" ? "bg-blue-50 border-blue-500" : "bg-red-50 border-red-500"}`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold">{role.name}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${role.team === "good" ? "bg-blue-200 text-blue-800" : "bg-red-200 text-red-800"}`}>
                      {role.team}
                    </span>
                  </div>
                  <p className="text-xs text-gray-600">{role.desc}</p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="font-bold text-gray-800 mb-3">Team Sizes</h3>
            <div className="overflow-x-auto">
              <table className="text-xs w-full">
                <thead>
                  <tr className="bg-gray-100">
                    <th className="p-2 text-left">Players</th>
                    <th className="p-2">M1</th><th className="p-2">M2</th><th className="p-2">M3</th><th className="p-2">M4</th><th className="p-2">M5</th>
                    <th className="p-2">Good</th><th className="p-2">Evil</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    [5, 2,3,2,3,3, 3,2], [6, 2,3,4,3,4, 4,2], [7, 2,3,3,"4*",4, 4,3],
                    [8, 3,4,4,"5*",5, 5,3], [9, 3,4,4,"5*",5, 6,3], [10, 3,4,4,"5*",5, 6,4],
                  ].map(([p, ...rest]) => (
                    <tr key={p as number} className="border-t border-gray-100">
                      <td className="p-2 font-medium">{p}</td>
                      {rest.map((v, i) => <td key={i} className="p-2 text-center">{v}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-gray-500 mt-1">* = requires 2 fail votes</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
