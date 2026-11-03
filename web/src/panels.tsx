import { Badge } from "./ui";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "./ui";
import { createContext, useContext, type ReactNode } from "react";

/** What a Choice does when pressed: it puts its prompt in the box and sends it, like typing. */
export const SendContext = createContext<(prompt: string) => void>(() => {});
export const useSend = () => useContext(SendContext);

export function Panel({ title, note, children, wide }: { title: string; note?: string; children: ReactNode; wide?: boolean }) {
  return (
    <Card className={`min-w-0 gap-3 py-4 ${wide ? "col-span-full" : ""}`}>
      <CardHeader className="px-4">
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
        {note && <CardDescription className="font-mono text-xs">{note}</CardDescription>}
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col gap-3 px-4">{children}</CardContent>
    </Card>
  );
}

/* Colour is never alone: every status carries its word and a mark. */
export function Status({ value }: { value: string }) {
  const ok = value === "pass" || value === "match";
  const bad = value === "fail" || value === "mismatch";
  return (
    <Badge variant="outline" className={`font-mono text-xs ${ok ? "border-success text-success" : bad ? "border-destructive text-destructive" : "text-muted-foreground"}`}>
      {ok ? "✓ " : bad ? "✕ " : ""}{value}
    </Badge>
  );
}

export function Waiting({ error }: { error?: string }) {
  return <Card className="px-4 py-3 text-xs text-muted-foreground">{error ? `No evidence here: ${error}` : "Loading evidence…"}</Card>;
}

export const LAYER_COLOURS: Record<string, string> = { nwell: "#8fb6c2", diff: "#34c77b", poly: "#f2562b", li1: "#a78bfa", met1: "#278ef7", licon: "#f2f5fa", mcon: "#22d3ee" };
