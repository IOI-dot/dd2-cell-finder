import { createContext, useContext, type ComponentProps } from "react";

const cn = (...parts: (string | false | undefined)[]) => parts.filter(Boolean).join(" ");

const BUTTON = {
  default: "bg-primary text-primary-foreground hover:bg-primary/90",
  destructive: "bg-destructive text-white hover:bg-destructive/90",
  outline: "border border-input bg-background hover:bg-accent",
  ghost: "hover:bg-accent",
};

export function Button({ className, variant = "default", size = "default", type = "button", ...p }: ComponentProps<"button"> & { variant?: keyof typeof BUTTON; size?: "default" | "sm" | "icon" }) {
  return <button type={type} className={cn("inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-md text-sm font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50", size === "icon" ? "size-11" : size === "sm" ? "h-8 px-3" : "h-9 px-4", BUTTON[variant], className)} {...p} />;
}

export const Badge = ({ className, variant: _, ...p }: ComponentProps<"span"> & { variant?: "outline" }) =>
  <span className={cn("inline-flex w-fit shrink-0 items-center justify-center gap-1 rounded-full border border-border px-2 py-0.5 text-xs font-medium whitespace-nowrap", className)} {...p} />;

export const Card = ({ className, ...p }: ComponentProps<"div">) => <div className={cn("flex flex-col rounded-xl border bg-card", className)} {...p} />;
export const CardHeader = ({ className, ...p }: ComponentProps<"div">) => <div className={cn("flex flex-col gap-1", className)} {...p} />;
export const CardContent = (p: ComponentProps<"div">) => <div {...p} />;
export const CardTitle = ({ className, ...p }: ComponentProps<"div">) => <div className={cn("font-semibold", className)} {...p} />;
export const CardDescription = ({ className, ...p }: ComponentProps<"div">) => <div className={cn("text-sm text-muted-foreground", className)} {...p} />;

export const Spinner = ({ className }: { className?: string }) =>
  <svg role="img" aria-label="Working" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className={cn("size-4 animate-spin", className)}><path d="M21 12a9 9 0 1 1-6.2-8.6" /></svg>;

export const Textarea = ({ className, ...p }: ComponentProps<"textarea">) =>
  <textarea className={cn("w-full rounded-md border border-input bg-transparent px-3 py-2 outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring", className)} {...p} />;

export const Slider = ({ value, onValueChange, className, ...p }: Omit<ComponentProps<"input">, "value"> & { value: number[]; onValueChange: (v: number[]) => void }) =>
  <input type="range" value={value[0]} onChange={(e) => onValueChange([+e.target.value])} className={cn("w-full accent-primary", className)} {...p} />;

export const Table = ({ className, ...p }: ComponentProps<"table">) => <table className={cn("w-full text-sm", className)} {...p} />;
export const TableHeader = ({ className, ...p }: ComponentProps<"thead">) => <thead className={cn("[&_tr]:border-b", className)} {...p} />;
export const TableBody = ({ className, ...p }: ComponentProps<"tbody">) => <tbody className={cn("[&_tr:last-child]:border-0", className)} {...p} />;
export const TableRow = ({ className, ...p }: ComponentProps<"tr">) => <tr className={cn("border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted", className)} {...p} />;
export const TableHead = ({ className, ...p }: ComponentProps<"th">) => <th className={cn("h-10 px-2 text-left align-middle font-medium whitespace-nowrap", className)} {...p} />;
export const TableCell = ({ className, ...p }: ComponentProps<"td">) => <td className={cn("p-2 align-middle whitespace-nowrap", className)} {...p} />;

const TabContext = createContext<{ value: string; onValueChange: (v: string) => void }>({ value: "", onValueChange: () => {} });

export const Tabs = ({ value, onValueChange, children }: { value: string; onValueChange: (v: string) => void; children: React.ReactNode }) =>
  <TabContext.Provider value={{ value, onValueChange }}>{children}</TabContext.Provider>;

export const TabsList = ({ className, ...p }: ComponentProps<"div">) => <div role="tablist" className={cn("inline-flex w-fit items-center rounded-lg bg-muted p-[3px] text-muted-foreground", className)} {...p} />;

export function TabsTrigger({ value, className, ...p }: ComponentProps<"button"> & { value: string }) {
  const tabs = useContext(TabContext);
  const on = tabs.value === value;
  return <button type="button" role="tab" aria-selected={on} onClick={() => tabs.onValueChange(value)} className={cn("inline-flex cursor-pointer items-center justify-center rounded-md px-2 py-1 text-sm font-medium whitespace-nowrap focus-visible:ring-2 focus-visible:ring-ring", on && "bg-background text-foreground", className)} {...p} />;
}
