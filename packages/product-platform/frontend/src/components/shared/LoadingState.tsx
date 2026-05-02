export function LoadingState({ label = "Loading workspace" }: { label?: string }) {
  return (
    <div
      className="rounded-lg border border-dashed bg-card p-6 text-sm text-muted-foreground"
      role="status"
    >
      {label}
    </div>
  );
}

