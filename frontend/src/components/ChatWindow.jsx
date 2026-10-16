import ReasoningPanel from './ReasoningPanel';
import '../styles/intel.css';

const BUDGET = 16384;
const STRIKE_MARKER = '[removed: unverifiable reference]';
const WARN_CODES = new Set(['UNGROUNDED_CITATION', 'UNSOURCED_QUANTITY', 'ANSWER_EDITED']);

/**
 * §14.2 changes 1–5:
 *  2. reasoning panel (collapsed, "not a finding");
 *  3. citation chips deep-linking to the FIR detail view;
 *  4. amber warning banner for UNGROUNDED_CITATION / UNSOURCED_QUANTITY with
 *     the offending text struck through inline;
 *  5. context meter (prompt_tokens / budget from meta — a credibility signal).
 */
function StruckAnswer({ text }) {
  if (!text.includes(STRIKE_MARKER)) {
    return <p className="msg-text">{text}</p>;
  }
  const parts = text.split(STRIKE_MARKER);
  return (
    <p className="msg-text">
      {parts.map((part, idx) => (
        <span key={idx}>
          {idx > 0 && <del className="struck">{STRIKE_MARKER}</del>}
          {part}
        </span>
      ))}
    </p>
  );
}

function CitationChips({ citations, onOpenFir }) {
  if (!citations || !citations.length) return null;
  return (
    <div className="citation-chips">
      {citations.map((cite, idx) => (
        <button
          key={`${cite.fir_id}-${idx}`}
          type="button"
          className="citation-chip"
          title={cite.station ? `FIR ${cite.fir_id} @ ${cite.station}` : `FIR ${cite.fir_id}`}
          onClick={() => onOpenFir && onOpenFir(cite.fir_id)}
        >
          📄 {cite.fir_id}
        </button>
      ))}
    </div>
  );
}

function WarningBanner({ warnings }) {
  const shown = (warnings || []).filter((w) => WARN_CODES.has(w.code));
  if (!shown.length) return null;
  return (
    <div className="warning-banner" role="alert">
      {shown.map((w, idx) => (
        <div key={idx} className="warning-item">
          ⚠ {w.code === 'UNGROUNDED_CITATION'
            ? `unverifiable reference${(w.ids || []).length ? ` (${(w.ids || []).join(', ')})` : ''} removed from the answer`
            : w.detail || w.code}
        </div>
      ))}
    </div>
  );
}

function ContextMeter({ meta }) {
  if (!meta || typeof meta.prompt_tokens !== 'number') return null;
  const used = Math.min(meta.prompt_tokens / BUDGET, 1);
  return (
    <div className="context-meter" title={`${meta.prompt_tokens} / ${BUDGET} prompt tokens`}>
      <div className="context-bar">
        <div className="context-fill" style={{ width: `${used * 100}%` }} />
      </div>
      <span className="context-label">
        context {meta.prompt_tokens}/{BUDGET}
      </span>
    </div>
  );
}

function MessageBubble({ message, onOpenFir, warnings, meta }) {
  const isUser = message.role === 'user';
  return (
    <div className={`flex mb-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${
        isUser
          ? 'bg-blue-600 text-white rounded-br-none'
          : 'bg-gray-200 text-gray-900 rounded-bl-none'
      }`}>
        {!isUser && <ReasoningPanel reasoning={message.reasoning} />}
        {isUser
          ? <p className="msg-text">{message.text}</p>
          : <StruckAnswer text={message.text} />}
        {!isUser && <CitationChips citations={message.citations} onOpenFir={onOpenFir} />}
        {!isUser && <WarningBanner warnings={warnings} />}
        {!isUser && <ContextMeter meta={meta} />}
        <p className="text-xs opacity-70 mt-2">{message.timestamp}</p>
      </div>
    </div>
  );
}

export default function ChatWindow({ chatHistory = [], warnings = [], meta = null, onOpenFir }) {
  return (
    <div className="flex flex-col h-96 bg-white rounded-lg border border-gray-200 p-4 overflow-y-auto">
      {chatHistory.length === 0 ? (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>No messages yet. Ask a question about the FIR records.</p>
        </div>
      ) : (
        chatHistory.map((msg) => (
          <MessageBubble key={msg.id} message={msg} onOpenFir={onOpenFir} warnings={warnings} meta={meta} />
        ))
      )}
    </div>
  );
}
