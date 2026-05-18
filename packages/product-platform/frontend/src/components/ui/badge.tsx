import type { HTMLAttributes } from "react";

import { cn } from "../../lib/utils";

type BadgeTone = "default" | "success" | "warning" | "danger" | "muted";

const tones: Record<BadgeTone, string> = {
  default: "border-transparent bg-primary text-primary-foreground",
  success:
    "border-[hsl(var(--status-success-border))] bg-[hsl(var(--status-success-bg))] text-[hsl(var(--status-success-fg))]",
  warning:
    "border-[hsl(var(--status-warning-border))] bg-[hsl(var(--status-warning-bg))] text-[hsl(var(--status-warning-fg))]",
  danger:
    "border-[hsl(var(--status-danger-border))] bg-[hsl(var(--status-danger-bg))] text-[hsl(var(--status-danger-fg))]",
  muted: "border-border/80 bg-muted/70 text-muted-foreground"
};

export function Badge({
  className,
  tone = "default",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold leading-5",
        tones[tone],
        className
      )}
      {...props}
    />
  );
}
