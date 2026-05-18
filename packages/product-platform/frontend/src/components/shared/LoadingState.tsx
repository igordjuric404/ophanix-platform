export function LoadingState({ label = "Loading workspace" }: { label?: string }) {
  return (
    <div
      className="m-6 rounded-lg border border-dashed border-border/80 bg-card p-6 text-sm text-muted-foreground shadow-[var(--shadow-panel)]"
      role="status"
    >
      {label}
    </div>
  );
}
