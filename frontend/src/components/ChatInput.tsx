import { ArrowUp, FileText, Image as ImageIcon, Paperclip, Sparkles, X } from "lucide-react";
import { useRef, useState } from "react";

const ACCEPTED = ".pdf,.png,.jpg,.jpeg,.webp,.docx,.txt";
const MAX_FILES = 5;
const MAX_BYTES = 15 * 1024 * 1024;

interface ChatInputProps {
  onSend: (question: string, files: File[]) => Promise<boolean> | boolean;
  disabled?: boolean;
  onSimplify: () => void;
}

export default function ChatInput({ onSend, disabled, onSimplify }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function addFiles(selected: FileList | null) {
    if (!selected) return;
    setFileError("");
    const incoming = Array.from(selected);
    const valid: File[] = [];
    for (const file of incoming) {
      const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
      if (!ACCEPTED.split(",").includes(extension)) {
        setFileError(`${file.name}: unsupported file type.`);
        continue;
      }
      if (file.size > MAX_BYTES) {
        setFileError(`${file.name}: files must be 15 MB or smaller.`);
        continue;
      }
      if (files.some((item) => item.name === file.name && item.size === file.size) || valid.some((item) => item.name === file.name && item.size === file.size)) continue;
      valid.push(file);
    }
    if (files.length + valid.length > MAX_FILES) {
      setFileError(`Attach up to ${MAX_FILES} files per message.`);
      setFiles((current) => [...current, ...valid].slice(0, MAX_FILES));
    } else {
      setFiles((current) => [...current, ...valid]);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = value.trim();
    if ((!question && files.length === 0) || disabled) return;
    const prompt = question || "Please analyze the attached file and help me study it.";
    const success = await onSend(prompt, files);
    if (success) {
      setValue("");
      setFiles([]);
      setFileError("");
      if (inputRef.current) inputRef.current.style.height = "auto";
    }
  }

  function resize() {
    const element = inputRef.current;
    if (element) {
      element.style.height = "auto";
      element.style.height = `${Math.min(element.scrollHeight, 150)}px`;
    }
  }

  return (
    <div className="composer-wrap">
      <form className="composer" onSubmit={submit}>
        {files.length > 0 && <div className="attachment-list" aria-label="Selected attachments">
          {files.map((file, index) => <div className="attachment-chip" key={`${file.name}-${file.size}-${index}`}>
            {file.type.startsWith("image/") ? <ImageIcon size={15} /> : <FileText size={15} />}
            <span title={file.name}>{file.name}</span>
            <button type="button" aria-label={`Remove ${file.name}`} onClick={() => setFiles((current) => current.filter((_, i) => i !== index))}><X size={13} /></button>
          </div>)}
        </div>}
        <textarea
          ref={inputRef}
          value={value}
          onChange={(event) => { setValue(event.target.value); resize(); }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
          placeholder="Ask anything from your textbooks…"
          rows={1}
          aria-label="Your question"
          disabled={disabled}
        />
        <div className="composer-bottom">
          <div className="composer-tools">
            <input ref={fileInputRef} type="file" accept={ACCEPTED} multiple hidden onChange={(event) => addFiles(event.currentTarget.files)} />
            <button type="button" className="composer-tool" title="Attach PDF, image, DOCX or TXT" onClick={() => fileInputRef.current?.click()} disabled={disabled || files.length >= MAX_FILES}><Paperclip size={16} /><span>Attach files</span></button>
            <button type="button" className="composer-tool simplify-tool" onClick={onSimplify} disabled={disabled}><Sparkles size={15} /><span>Explain simpler</span></button>
          </div>
          <div className="composer-send-area"><span className="enter-hint">↵ to send</span><button type="submit" className="send-button" disabled={(!value.trim() && files.length === 0) || disabled} aria-label="Send question"><ArrowUp size={19} /></button></div>
        </div>
      </form>
      {fileError && <p className="attachment-error" role="alert">{fileError}</p>}
      <p className="composer-note">PDF, images, DOCX and TXT · Max 15 MB each, up to 5 files. StudyWise can make mistakes.</p>
    </div>
  );
}
