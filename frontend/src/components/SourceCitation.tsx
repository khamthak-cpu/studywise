import { BookOpen, ExternalLink } from "lucide-react";
import type { Source } from "../types";

export default function SourceCitation({ source, index }: { source: Source; index: number }) {
  const label = [source.chapter, source.page ? `p. ${source.page}` : undefined].filter(Boolean).join(" · ");
  return (
    <article className="source-card">
      <div className="source-icon"><BookOpen size={17} /></div>
      <div className="source-copy">
        <div className="source-title">{index + 1}. {source.title}</div>
        <div className="source-meta">{label || "Reference"}</div>
        {source.excerpt && <p className="source-excerpt">{source.excerpt}</p>}
      </div>
      {source.url && <a className="source-link" href={source.url} target="_blank" rel="noreferrer" aria-label="Open source"><ExternalLink size={15} /></a>}
    </article>
  );
}