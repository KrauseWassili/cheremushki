type LoadingStateProps = {
  title?: string;
  lines?: number;
};

export function LoadingState({
  title = "Загрузка",
  lines = 3,
}: LoadingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="mx-auto w-full max-w-3xl py-10"
    >
      <span className="sr-only">{title}</span>
      <div className="grid gap-4">
        <div className="h-7 w-48 animate-pulse rounded-full bg-muted/70" />
        {Array.from({ length: lines }).map((_, index) => (
          <div
            key={index}
            className="rounded-3xl border border-border bg-background p-5 shadow-sm"
          >
            <div className="flex gap-4">
              <div className="size-20 shrink-0 animate-pulse rounded-2xl bg-muted/70" />
              <div className="grid flex-1 gap-3">
                <div className="h-5 w-2/3 animate-pulse rounded-full bg-muted/70" />
                <div className="h-4 w-1/2 animate-pulse rounded-full bg-muted/60" />
                <div className="h-4 w-full animate-pulse rounded-full bg-muted/50" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
