import { BadgeCheck, CircleHelp } from "lucide-react";

export default function ConfidenceBadge({ confidence }: { confidence: string }) {
  const grounded = confidence === "grounded";
  return (
    <span className={`confidence-badge ${grounded ? "grounded" : "uncertain"}`}>
      {grounded ? <BadgeCheck size={14} /> : <CircleHelp size={14} />}
      {grounded ? "Source-grounded" : "Needs verification"}
    </span>
  );
}