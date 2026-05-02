import { Badge } from "../ui/badge";

export function RiskBadge({ risk }: { risk: string }) {
  const normalized = risk.toLowerCase();
  const tone =
    normalized === "critical" || normalized === "high"
      ? "danger"
      : normalized === "medium"
        ? "warning"
        : "success";
  return <Badge tone={tone}>{risk}</Badge>;
}

