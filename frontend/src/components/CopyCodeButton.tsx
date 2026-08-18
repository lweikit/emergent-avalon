import { useState, useRef, useEffect, useCallback } from "react";

interface CopyCodeButtonProps {
  code: string;
  className?: string;
}

/**
 * Copies the room code, and says so.
 *
 * navigator.clipboard is undefined on insecure origins, which includes the plain
 * HTTP LAN addresses people actually use to get friends into a game -- so the
 * write is feature-detected and failure is surfaced instead of thrown.
 */
export default function CopyCodeButton({ code, className = "" }: CopyCodeButtonProps) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const copy = useCallback(async () => {
    if (timer.current) clearTimeout(timer.current);
    let ok = false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(code);
        ok = true;
      }
    } catch {
      ok = false;
    }
    setStatus(ok ? "copied" : "failed");
    timer.current = setTimeout(() => setStatus("idle"), 2000);
  }, [code]);

  const label =
    status === "copied" ? "Copied" : status === "failed" ? "Select to copy" : `Room: ${code}`;

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={`Room code ${code}. Copy to clipboard.`}
      title="Copy room code"
      className={`bg-gray-700 hover:bg-gray-600 text-gray-200 px-3 py-2 rounded transition-colors min-h-[44px] font-mono tracking-wider ${className}`}
    >
      {status === "failed" ? <span className="select-all">{code}</span> : label}
      <span aria-live="polite" className="sr-only">
        {status === "copied" ? "Room code copied to clipboard" : ""}
      </span>
    </button>
  );
}
