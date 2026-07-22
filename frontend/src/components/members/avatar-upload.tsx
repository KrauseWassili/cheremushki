"use client";

import { useRef, useState } from "react";

type AvatarUploadProps = {
  value?: string;
  fullName: string;
  onChange: (value?: string) => void;
};

const allowedTypes = [
  "image/jpeg",
  "image/png",
  "image/webp",
];

const maxFileSize = 5 * 1024 * 1024;

export function AvatarUpload({
  value,
  fullName,
  onChange,
}: AvatarUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState("");

  function handleFileChange(
    event: React.ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setError("");

    if (!allowedTypes.includes(file.type)) {
      setError("Поддерживаются только JPG, PNG и WebP.");
      event.target.value = "";
      return;
    }

    if (file.size > maxFileSize) {
      setError("Файл не должен превышать 5 МБ.");
      event.target.value = "";
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      if (typeof reader.result === "string") {
        onChange(reader.result);
      }
    };

    reader.onerror = () => {
      setError("Не удалось прочитать файл.");
    };

    reader.readAsDataURL(file);
  }

  function handleRemove() {
    onChange(undefined);
    setError("");

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  return (
    <div>
      <p className="font-bold">Фотография</p>

      <div className="mt-3 flex flex-col gap-5 sm:flex-row sm:items-center">
        {value ? (
          <img
            src={value}
            alt={`Аватар ${fullName}`}
            className="size-28 rounded-2xl object-cover"
          />
        ) : (
          <div className="flex size-28 items-center justify-center rounded-2xl bg-muted text-3xl font-black">
            {fullName.charAt(0).toUpperCase()}
          </div>
        )}

        <div>
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleFileChange}
            className="sr-only"
            id="avatar-upload"
          />

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="rounded-xl border border-border px-4 py-2.5 text-sm font-bold hover:bg-muted"
            >
              {value ? "Заменить фотографию" : "Загрузить фотографию"}
            </button>

            {value && (
              <button
                type="button"
                onClick={handleRemove}
                className="rounded-xl px-4 py-2.5 text-sm font-bold text-red-700 hover:bg-red-50"
              >
                Удалить
              </button>
            )}
          </div>

          <p className="mt-3 text-xs text-muted-foreground">
            JPG, PNG или WebP. Не более 5 МБ.
          </p>

          {error && (
            <p role="alert" className="mt-2 text-sm text-red-700">
              {error}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}