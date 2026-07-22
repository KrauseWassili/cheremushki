import Link from "next/link";

type JoinNavigationProps = {
  previousHref?: string;
  nextHref?: string;

  previousLabel?: string;
  nextLabel?: string;

  nextDisabled?: boolean;
};

export function JoinNavigation({
  previousHref,
  nextHref,
  previousLabel = "Назад",
  nextLabel = "Дальше",
  nextDisabled = false,
}: JoinNavigationProps) {
  return (
    <div className="mt-10 flex flex-col-reverse gap-3 border-t border-border pt-6 sm:flex-row sm:justify-between">
      {previousHref ? (
        <Link
          href={previousHref}
          className="inline-flex min-h-11 items-center justify-center rounded-xl border border-border px-5 text-sm font-bold transition hover:bg-muted"
        >
          ← {previousLabel}
        </Link>
      ) : (
        <div />
      )}

      {nextHref && !nextDisabled ? (
        <Link
          href={nextHref}
          className="inline-flex min-h-11 items-center justify-center rounded-xl bg-foreground px-5 text-sm font-bold text-background transition hover:opacity-85"
        >
          {nextLabel} →
        </Link>
      ) : nextHref ? (
        <button
          type="button"
          disabled
          className="min-h-11 cursor-not-allowed rounded-xl bg-muted px-5 text-sm font-bold text-muted-foreground"
        >
          {nextLabel} →
        </button>
      ) : null}
    </div>
  );
}