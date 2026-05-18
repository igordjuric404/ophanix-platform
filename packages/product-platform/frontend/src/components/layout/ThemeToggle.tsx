import { Monitor, Moon, Sun } from "lucide-react";

import { useTheme } from "../../app/themeContext";
import { Button } from "../ui/button";

const nextTheme = {
  light: "dark",
  dark: "system",
  system: "light"
} as const;

const themeLabels = {
  light: "Light",
  dark: "Dark",
  system: "System"
} as const;

export function ThemeToggle() {
  const { preference, resolvedTheme, setPreference } = useTheme();
  const Icon = preference === "system" ? Monitor : resolvedTheme === "dark" ? Moon : Sun;

  return (
    <Button
      aria-label={`Theme: ${themeLabels[preference]}. Switch theme`}
      className="h-9 w-9 p-0"
      onClick={() => setPreference(nextTheme[preference])}
      title={`Theme: ${themeLabels[preference]}`}
      type="button"
      variant="outline"
    >
      <Icon className="h-4 w-4" />
    </Button>
  );
}
