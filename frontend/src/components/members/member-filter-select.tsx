type MemberFilterSelectProps = {
  id: string;
  label: string;
  value: string;
  options: string[];
  placeholder: string;
  onChange: (value: string) => void;
};

export function MemberFilterSelect({
  id,
  label,
  value,
  options,
  placeholder,
  onChange,
}: MemberFilterSelectProps) {
  return (
    <label htmlFor={id} className="grid gap-2">
      <span className="text-sm font-bold">{label}</span>

      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 rounded-xl border border-border bg-background pl-3 text-sm outline-none transition focus:border-foreground/40 focus:ring-4 focus:ring-foreground/5"
      >
        <option value="">{placeholder}</option>

        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
