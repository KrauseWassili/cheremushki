import type {
  InputHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

type FieldSize = "md" | "lg";

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  fieldSize?: FieldSize;
};

type TextAreaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  fieldSize?: FieldSize;
};

export function TextField({
  fieldSize = "md",
  className,
  ...props
}: TextFieldProps) {
  return (
    <input
      {...props}
      className={fieldClassName({ size: fieldSize, className })}
    />
  );
}

export function TextArea({
  fieldSize = "md",
  className,
  ...props
}: TextAreaProps) {
  return (
    <textarea
      {...props}
      className={fieldClassName({ multiline: true, size: fieldSize, className })}
    />
  );
}

export function fieldClassName({
  multiline = false,
  size = "md",
  className,
}: {
  multiline?: boolean;
  size?: FieldSize;
  className?: string;
} = {}) {
  return [
    multiline ? "min-h-28 py-3" : size === "lg" ? "h-14" : "h-11",
    "w-full rounded-xl border border-border bg-input-background px-3 text-foreground shadow-inner outline-none transition",
    "placeholder:text-muted-foreground focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5 disabled:opacity-60",
    className,
  ]
    .filter(Boolean)
    .join(" ");
}
