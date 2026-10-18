import { Languages, Sparkles } from "lucide-react";

interface ModeToggleProps {
  mode: "normal" | "simplify";
  onModeChange: (mode: "normal" | "simplify") => void;
  language: "en" | "hi";
  onLanguageChange: (language: "en" | "hi") => void;
}

export default function ModeToggle({ mode, onModeChange, language, onLanguageChange }: ModeToggleProps) {
  return (
    <div className="study-controls">
      <div className="segmented" role="group" aria-label="Explanation style">
        <button className={mode === "normal" ? "active" : ""} onClick={() => onModeChange("normal")}><Sparkles size={14} /> Standard</button>
        <button className={mode === "simplify" ? "active" : ""} onClick={() => onModeChange("simplify")}><Sparkles size={14} /> Simple</button>
      </div>
      <label className="language-select"><Languages size={15} /><select value={language} onChange={(event) => onLanguageChange(event.target.value as "en" | "hi")} aria-label="Response language"><option value="en">English</option><option value="hi">Hindi</option></select></label>
    </div>
  );
}