import { Badge } from "../ui/badge";

export function StatusBadge({ status }: { status?: string | null }) {
  const label = status || "unknown";
  const normalized = label.toLowerCase();
  const tone =
    normalized.includes("healthy") || normalized.includes("active")
      ? "success"
      : normalized.includes("warn") || normalized.includes("degraded")
        ? "warning"
        : normalized.includes("fail") || normalized.includes("error")
          ? "danger"
          : "muted";
  return <Badge tone={tone}>{label}</Badge>;
}
