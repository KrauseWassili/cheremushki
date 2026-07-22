type JoinPageHeaderProps = {
  eyebrow?: string;
  title: string;
  description: string;
};

export function JoinPageHeader({
  eyebrow,
  title,
  description,
}: JoinPageHeaderProps) {
  return (
    <header>
      {eyebrow && (
        <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
          {eyebrow}
        </p>
      )}

      <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
        {title}
      </h1>

      <p className="mt-4 max-w-xl leading-7 text-muted-foreground">
        {description}
      </p>
    </header>
  );
}