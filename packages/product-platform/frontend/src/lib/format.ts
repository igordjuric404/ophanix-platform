export function formatNumber(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "0";
  }
  return new Intl.NumberFormat("en-US").format(value);
}

export function sentenceCase(value: string) {
  if (!value) {
    return "";
  }
  return `${value.slice(0, 1).toUpperCase()}${value.slice(1).replace(/[-_]/g, " ")}`;
}

