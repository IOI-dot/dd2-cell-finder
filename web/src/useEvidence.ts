import { useEffect, useState } from "react";

/** Numbers reach a panel only from here: a handle goes to the read-only API, never a value. */
export function useEvidence<T>(handle: string | undefined, view?: string) {
  const [state, setState] = useState<{ data?: T; error?: string }>({});
  useEffect(() => {
    if (!handle) return;
    let live = true;
    const url = `/api/evidence/${handle}${view ? `?view=${view}` : ""}`;
    fetch(url)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status}`))))
      .then((data) => live && setState({ data }))
      .catch((e) => live && setState({ error: String(e.message ?? e) }));
    return () => {
      live = false;
    };
  }, [handle, view]);
  return state;
}
