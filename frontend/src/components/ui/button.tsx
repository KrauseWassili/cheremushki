import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "solid";
type ButtonSize = "sm" | "md" | "lg";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      className={buttonClassName({ variant, size, className })}
    >
      {children}
    </button>
  );
}

export function buttonClassName({
  variant = "secondary",
  size = "md",
  className,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
} = {}) {
  return [
    "inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-60",
    variantClassName[variant],
    sizeClassName[size],
    className,
  ]
    .filter(Boolean)
    .join(" ");
}

const variantClassName: Record<ButtonVariant, string> = {
  primary: "border border-transparent bg-primary text-surface hover:bg-primary-hover",
  secondary: "border border-border text-foreground hover:bg-muted",
  danger: "border border-destructive/30 text-destructive hover:bg-danger-soft",
  solid: "border border-transparent bg-foreground text-background hover:bg-foreground/90",
};

const sizeClassName: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5",
  md: "px-4 py-2.5",
  lg: "px-5 py-3",
};
