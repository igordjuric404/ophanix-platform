export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border/80 bg-card p-6">
      <div className="font-display font-semibold">{title}</div>
      <p className="mt-1 text-sm leading-5 text-muted-foreground">{description}</p>
    </div>
  );
}
