import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

export function MetricCard({
  icon,
  label,
  value,
  detail
}: {
  icon?: ReactNode;
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            {label}
          </CardTitle>
          {icon ? (
            <span className="flex h-8 w-8 items-center justify-center rounded-md border border-border/80 bg-muted/70 text-brand-teal">
              {icon}
            </span>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        <div className="break-words font-display text-3xl font-semibold leading-none">{value}</div>
        {detail ? <p className="mt-2 text-sm leading-5 text-muted-foreground">{detail}</p> : null}
      </CardContent>
    </Card>
  );
}
