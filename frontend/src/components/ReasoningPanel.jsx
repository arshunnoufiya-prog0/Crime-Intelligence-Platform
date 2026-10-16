import { useState } from 'react';

/**
 * §14.2 change 2 — reasoning panel. Collapsed by default, visually distinct
 * from the answer, and explicitly labeled as NOT a finding (§1.3 rule 2).
 */
export default function ReasoningPanel({ reasoning }) {
  const [open, setOpen] = useState(false);
  if (!reasoning || !reasoning.trim()) return null;

  return (
    <div className="reasoning-panel">
      <button
        type="button"
        className="reasoning-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {open ? '▾' : '▸'} model reasoning — not a finding
      </button>
      {open && (
        <pre className="reasoning-body">{reasoning}</pre>
      )}
    </div>
  );
}
