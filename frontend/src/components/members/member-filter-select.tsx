import { CustomSelect } from "@/components/ui/custom-select";

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

      <CustomSelect
        id={id}
        value={value}
        placeholder={placeholder}
        onChange={onChange}
        options={[
          { value: "", label: placeholder },
          ...options.map((option) => ({ value: option, label: option })),
        ]}
      />
    </label>
  );
}
