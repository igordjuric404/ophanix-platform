import { Badge } from "../ui/badge";

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const tone =
    normalized.includes("healthy") || normalized.includes("active")
      ? "success"
      : normalized.includes("warn") || normalized.includes("degraded")
        ? "warning"
        : normalized.includes("fail") || normalized.includes("error")
          ? "danger"
          : "muted";
  return <Badge tone={tone}>{status}</Badge>;
}

