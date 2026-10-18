import { Cloud, CloudOff, Wifi, WifiOff } from "lucide-react";

interface StatusBarProps {
  mode: "offline" | "online" | "checking" | "unavailable";
  mockMode: boolean;
}

export default function StatusBar({ mode, mockMode }: StatusBarProps) {
  const isOnline = mode === "online";
  const isUnavailable = mode === "unavailable";
  const label = mockMode
    ? "Demo mode · sample answers"
    : isUnavailable
      ? "Backend unavailable"
      : mode === "checking"
        ? "Checking backend…"
        : isOnline
          ? "Online search available"
          : "Local mode";

  return (
    <div className={`status-pill ${isUnavailable ? "status-error" : ""}`}>
      {mockMode ? <Cloud size={14} /> : isUnavailable ? <WifiOff size={14} /> : isOnline ? <Wifi size={14} /> : <CloudOff size={14} />}
      <span>{label}</span>
      <span className="status-dot" />
    </div>
  );
}