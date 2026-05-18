import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  action
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-3 border-b border-border/80 bg-background/75 px-4 py-5 backdrop-blur md:flex-row md:items-center md:justify-between md:px-6">
      <div>
        <h1 className="font-display text-2xl font-semibold tracking-normal md:text-3xl">{title}</h1>
        <p className="mt-1 max-w-3xl text-sm leading-5 text-muted-foreground">{description}</p>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}
