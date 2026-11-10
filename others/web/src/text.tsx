const SUB = "₀₁₂₃₄₅₆₇₈₉";

/** Helper nets read as engineers write them: _s1 becomes s₁. Names such as web_cell_r0 stay as they are. */
export const pretty = (t: string) => t.replace(/(?<![A-Za-z0-9_])_([A-Za-z]+)(\d+)(?![A-Za-z0-9_])/g, (_, name, n: string) => name + [...n].map((c) => SUB[+c]).join(""));

const TOKENS = /([!(]*[A-Za-z]\w*\)*(?:\s*[&|^]\s*[!(]*[A-Za-z]\w*\)*)+)|\b(r\d+)\b/g;

/** Text with its Boolean functions and build names picked out. */
export function Rich({ text }: { text: string }) {
  const out: React.ReactNode[] = [];
  let at = 0;
  for (const m of text.matchAll(TOKENS)) {
    out.push(pretty(text.slice(at, m.index)));
    out.push(m[1] ? <code key={m.index} className="rounded bg-primary/15 px-1 py-0.5 font-mono text-[0.85em] text-info">{m[1]}</code>
      : <code key={m.index} className="font-mono text-[0.9em] text-info">{m[2]}</code>);
    at = m.index + m[0].length;
  }
  out.push(pretty(text.slice(at)));
  return <>{out}</>;
}
