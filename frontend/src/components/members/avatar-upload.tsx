"use client";

import { type Dispatch, useRef, useState } from "react";
import { useEscapeKey } from "@/lib/use-escape-key";
import { Button } from "@/components/ui/button";
import { ModalFrame } from "@/components/ui/modal";

type AvatarUploadProps = {
  value?: string;
  sourceValue?: string;
  fullName: string;
  required?: boolean;
  positionX?: number;
  positionY?: number;
  scale?: number;
  cropSize?: number;
  onChange: Dispatch<string | undefined>;
  onSourceChange?: Dispatch<string | undefined>;
  onCropChange?: Dispatch<{
    x: number;
    y: number;
    scale: number;
    size: number;
    avatarUrl?: string;
    sourceUrl?: string;
  }>;
};

const allowedTypes = [
  "image/jpeg",
  "image/png",
  "image/webp",
];

const maxFileSize = 5 * 1024 * 1024;

export function AvatarUpload({
  value,
  sourceValue,
  fullName,
  required = false,
  positionX = 50,
  positionY = 50,
  scale = 1,
  cropSize,
  onChange,
  onSourceChange,
  onCropChange,
}: AvatarUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState("");
  const [isCropOpen, setIsCropOpen] = useState(false);
  const [localSourceValue, setLocalSourceValue] = useState<string | undefined>();
  const [imageSize, setImageSize] = useState({ width: 1, height: 1 });
  const [draftCrop, setDraftCrop] = useState({
    x: positionX,
    y: positionY,
    size: cropSize ?? clamp(100 / scale, 40, 100),
  });
  const [dragState, setDragState] = useState<{
    mode: "move" | "resize";
    pointerId: number;
    startClientX: number;
    startClientY: number;
    startX: number;
    startY: number;
    startSize: number;
  } | null>(null);

  const cropSource = sourceValue || localSourceValue || value;

  useEscapeKey(isCropOpen, () => setIsCropOpen(false));

  function openCropModal() {
    setDraftCrop({
      x: positionX,
      y: positionY,
      size: cropSize ?? clamp(100 / scale, 40, 100),
    });
    setIsCropOpen(true);
  }

  function updateDraftCrop(nextCrop: { x: number; y: number; size: number }) {
    const size = clamp(nextCrop.size, 20, 100);
    const bounds = getCropBounds(size, imageSize);
    setDraftCrop({
      size,
      x: clamp(nextCrop.x, bounds.minX, bounds.maxX),
      y: clamp(nextCrop.y, bounds.minY, bounds.maxY),
    });
  }

  async function commitCrop() {
    if (!cropSource) return;

    try {
      const croppedAvatar = await createCroppedAvatar(cropSource, draftCrop);
      onChange(croppedAvatar);
      onCropChange?.({
        x: draftCrop.x,
        y: draftCrop.y,
        size: draftCrop.size,
        scale: 100 / draftCrop.size,
        avatarUrl: croppedAvatar,
        sourceUrl: cropSource,
      });
      setIsCropOpen(false);
    } catch {
      setError("Не удалось применить кадрирование.");
    }
  }

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
        setLocalSourceValue(reader.result);
        onSourceChange?.(reader.result);
        onChange(reader.result);
        setDraftCrop({ x: 50, y: 50, size: 100 });
        setIsCropOpen(true);
      }
    };

    reader.onerror = () => {
      setError("Не удалось прочитать файл.");
    };

    reader.readAsDataURL(file);
  }

  function handleRemove() {
    onChange(undefined);
    onSourceChange?.(undefined);
    onCropChange?.({ x: 50, y: 50, scale: 1, size: 100 });
    setError("");

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  function handleFramePointerDown(
    event: React.PointerEvent<HTMLDivElement>,
  ) {
    if ((event.target as HTMLElement).dataset.cropHandle === "resize") return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragState({
      mode: "move",
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: draftCrop.x,
      startY: draftCrop.y,
      startSize: draftCrop.size,
    });
  }

  function handleResizePointerDown(
    event: React.PointerEvent<HTMLButtonElement>,
  ) {
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragState({
      mode: "resize",
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: draftCrop.x,
      startY: draftCrop.y,
      startSize: draftCrop.size,
    });
  }

  function handleFramePointerMove(
    event: React.PointerEvent<HTMLElement>,
  ) {
    if (!dragState || dragState.pointerId !== event.pointerId) return;

    const imageRect = getFittedImageRect(imageSize);
    const deltaX =
      ((event.clientX - dragState.startClientX) / (288 * imageRect.width / 100)) *
      100;
    const deltaY =
      ((event.clientY - dragState.startClientY) / (288 * imageRect.height / 100)) *
      100;

    if (dragState.mode === "move") {
      updateDraftCrop({
        ...draftCrop,
        x: dragState.startX + deltaX,
        y: dragState.startY + deltaY,
      });
      return;
    }

    const minImageSidePx =
      288 * Math.min(imageRect.width, imageRect.height) / 100;
    const deltaSize = Math.max(
      event.clientX - dragState.startClientX,
      event.clientY - dragState.startClientY,
    ) / minImageSidePx * 100;

    updateDraftCrop({
      x: dragState.startX,
      y: dragState.startY,
      size: dragState.startSize + deltaSize * 2,
    });
  }

  function handleFramePointerEnd(event: React.PointerEvent<HTMLElement>) {
    if (dragState?.pointerId === event.pointerId) {
      setDragState(null);
    }
  }

  return (
    <div>
      <p className="flex items-center justify-between gap-3 font-bold">
        <span>Фотография</span>
        {required && (
          <span
            className={[
              "rounded-full px-2 py-0.5 text-[11px] font-bold",
              value
                ? "bg-success-soft text-success"
                : "bg-warning-soft text-warning",
            ].join(" ")}
          >
            {value ? "Заполнено" : "Обязательно"}
          </span>
        )}
      </p>

      <div className="mt-3 flex flex-col gap-5 min-[900px]:flex-row min-[900px]:items-center">
        {value ? (
          <img
            src={value}
            width={112}
            height={112}
            alt={`Аватар ${fullName}`}
            className={[
              "size-28 rounded-2xl border object-cover",
              required ? "border-success" : "border-border",
            ].join(" ")}
          />
        ) : (
          <div
            className={[
              "flex size-28 items-center justify-center rounded-2xl border bg-muted text-3xl font-black",
              required
                ? "border-warning bg-warning-soft/30"
                : "border-border",
            ].join(" ")}
          >
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
            aria-label="Загрузить фотографию профиля"
          />

          <div className="flex flex-wrap gap-3">
            <Button
              type="button"
              onClick={() => inputRef.current?.click()}
            >
              {value ? "Заменить" : "Загрузить"}
            </Button>

            {value && (
              <>
                <Button
                  type="button"
                  onClick={openCropModal}
                >
                  Настроить кадр
                </Button>

                <Button
                  type="button"
                  onClick={handleRemove}
                  variant="danger"
                >
                  Удалить
                </Button>
              </>
            )}
          </div>

          {error && (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {error}
            </p>
          )}
        </div>
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        JPG, PNG или WebP. Не более 5 МБ.
      </p>

      {cropSource && isCropOpen && (
        <ModalFrame label="Настройка фотографии" className="max-w-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-bold">Настройка фотографии</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Фото вписано в квадрат. Передвиньте рамку или потяните угол.
                </p>
                {!sourceValue && !localSourceValue && (
                  <p className="mt-2 text-xs font-bold text-warning">
                    Для старой аватарки доступен только текущий сохранённый кадр.
                    Загрузите фото заново, чтобы кадрировать исходник.
                  </p>
                )}
              </div>

              <Button
                type="button"
                onClick={() => setIsCropOpen(false)}
                size="sm"
              >
                Закрыть
              </Button>
            </div>

            <div className="mt-6 flex justify-center">
              <div
                role="presentation"
                onPointerMove={handleFramePointerMove}
                onPointerUp={handleFramePointerEnd}
                onPointerCancel={handleFramePointerEnd}
                className="relative size-72 touch-none overflow-hidden rounded-3xl border border-border bg-muted"
              >
                <img
                  src={cropSource}
                  alt={`Кадрирование ${fullName}`}
                  draggable={false}
                  onLoad={(event) =>
                    setImageSize({
                      width: event.currentTarget.naturalWidth || 1,
                      height: event.currentTarget.naturalHeight || 1,
                    })
                  }
                  className="size-full select-none object-contain"
                />

                <div
                  role="presentation"
                  onPointerDown={handleFramePointerDown}
                  style={{
                    ...getFrameStyle(draftCrop, imageSize),
                  }}
                  className="absolute cursor-move overflow-hidden rounded-3xl border-2 border-crop-frame bg-transparent shadow-[0_0_0_9999px_var(--color-crop-mask)]"
                >
                  <div className="pointer-events-none absolute inset-0 grid grid-cols-3 grid-rows-3">
                    {Array.from({ length: 9 }).map((_, index) => (
                      <div key={index} className="border border-crop-frame/35" />
                    ))}
                  </div>

                  <button
                    type="button"
                    aria-label="Изменить размер рамки"
                    data-crop-handle="resize"
                    onPointerDown={handleResizePointerDown}
                    onPointerMove={handleFramePointerMove}
                    onPointerUp={handleFramePointerEnd}
                    onPointerCancel={handleFramePointerEnd}
                    className="absolute -bottom-2 -right-2 size-5 cursor-nwse-resize rounded-full border-2 border-crop-frame bg-foreground"
                  />
                </div>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <Button
                type="button"
                onClick={() => setIsCropOpen(false)}
              >
                Отмена
              </Button>

              <Button
                type="button"
                onClick={commitCrop}
                variant="solid"
              >
                Готово
              </Button>
            </div>
        </ModalFrame>
      )}
    </div>
  );
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function getCropBounds(
  size: number,
  imageSize: { width: number; height: number },
) {
  const minSide = Math.min(imageSize.width, imageSize.height);
  const horizontalMargin = ((size / 100) * minSide) / imageSize.width / 2 * 100;
  const verticalMargin = ((size / 100) * minSide) / imageSize.height / 2 * 100;

  return {
    minX: horizontalMargin,
    maxX: 100 - horizontalMargin,
    minY: verticalMargin,
    maxY: 100 - verticalMargin,
  };
}

function getFittedImageRect(imageSize: { width: number; height: number }) {
  const aspectRatio = imageSize.width / imageSize.height;

  if (aspectRatio >= 1) {
    const height = 100 / aspectRatio;
    return {
      left: 0,
      top: (100 - height) / 2,
      width: 100,
      height,
    };
  }

  const width = aspectRatio * 100;
  return {
    left: (100 - width) / 2,
    top: 0,
    width,
    height: 100,
  };
}

function getFrameStyle(
  crop: { x: number; y: number; size: number },
  imageSize: { width: number; height: number },
) {
  const imageRect = getFittedImageRect(imageSize);
  const minSide = Math.min(imageSize.width, imageSize.height);
  const cropPixelSize = (crop.size / 100) * minSide;
  const frameWidth = (cropPixelSize / imageSize.width) * imageRect.width;
  const frameHeight = (cropPixelSize / imageSize.height) * imageRect.height;
  const frameLeft =
    imageRect.left + (crop.x / 100) * imageRect.width - frameWidth / 2;
  const frameTop =
    imageRect.top + (crop.y / 100) * imageRect.height - frameHeight / 2;

  return {
    left: `${frameLeft}%`,
    top: `${frameTop}%`,
    width: `${frameWidth}%`,
    height: `${frameHeight}%`,
  };
}

async function createCroppedAvatar(
  source: string,
  crop: { x: number; y: number; size: number },
) {
  const image = await loadImage(source);
  const minSide = Math.min(image.naturalWidth, image.naturalHeight);
  const cropPixelSize = (crop.size / 100) * minSide;
  const sourceX = clamp(
    (crop.x / 100) * image.naturalWidth - cropPixelSize / 2,
    0,
    image.naturalWidth - cropPixelSize,
  );
  const sourceY = clamp(
    (crop.y / 100) * image.naturalHeight - cropPixelSize / 2,
    0,
    image.naturalHeight - cropPixelSize,
  );

  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;

  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Canvas is not available");
  }

  context.drawImage(
    image,
    sourceX,
    sourceY,
    cropPixelSize,
    cropPixelSize,
    0,
    0,
    canvas.width,
    canvas.height,
  );

  return canvas.toDataURL("image/jpeg", 0.92);
}

function loadImage(source: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = source;
  });
}
