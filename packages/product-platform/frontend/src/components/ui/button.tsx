import { Slot } from "@radix-ui/react-slot";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

export type ButtonVariant = "default" | "secondary" | "outline" | "ghost" | "destructive";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
  variant?: ButtonVariant;
}

const variants: Record<ButtonVariant, string> = {
  default:
    "border-primary bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 hover:shadow",
  secondary:
    "border-border bg-secondary text-secondary-foreground hover:border-primary/30 hover:bg-secondary/80",
  outline:
    "border-border bg-background/80 text-foreground shadow-sm hover:border-primary/45 hover:bg-accent hover:text-accent-foreground",
  ghost:
    "border-transparent bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground",
  destructive:
    "border-destructive bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90"
};

export function Button({ asChild = false, className, variant = "default", ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  const buttonProps = asChild ? props : { type: "button" as const, ...props };
  return (
    <Comp
      className={cn(
        "inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium tracking-normal transition-all duration-150 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/20 disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        className
      )}
      {...buttonProps}
    />
  );
}
