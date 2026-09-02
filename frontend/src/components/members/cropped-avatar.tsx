"use client";

import { useState } from "react";

type CroppedAvatarProps = {
  src: string;
  originalSrc?: string;
  alt: string;
  className?: string;
  width: number;
  height: number;
  positionX?: number;
  positionY?: number;
  scale?: number;
  cropSize?: number;
  loading?: "eager" | "lazy";
  decoding?: "async" | "auto" | "sync";
  fetchPriority?: "high" | "low" | "auto";
};

export function CroppedAvatar({
  src,
  originalSrc,
  alt,
  className = "",
  width,
  height,
  positionX = 50,
  positionY = 50,
  scale = 1,
  cropSize,
  loading,
  decoding,
  fetchPriority,
}: CroppedAvatarProps) {
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const source = originalSrc || src;
  const preciseStyle =
    originalSrc && imageSize.width > 0 && imageSize.height > 0
      ? getCroppedImageStyle({
          imageSize,
          positionX,
          positionY,
          cropSize: cropSize ?? 100 / Math.max(scale, 1),
        })
      : null;

  return (
    <span
      className={["relative block shrink-0 overflow-hidden bg-muted", className].join(" ")}
      style={{ width, height }}
    >
      <img
        src={source}
        width={width}
        height={height}
        loading={loading}
        decoding={decoding}
        fetchPriority={fetchPriority}
        alt={alt}
        onLoad={(event) =>
          setImageSize({
            width: event.currentTarget.naturalWidth,
            height: event.currentTarget.naturalHeight,
          })
        }
        className={
          preciseStyle
            ? "absolute max-w-none"
            : "absolute inset-0 size-full object-cover"
        }
        style={preciseStyle ?? { objectPosition: `${positionX}% ${positionY}%` }}
      />
    </span>
  );
}

function getCroppedImageStyle({
  imageSize,
  positionX,
  positionY,
  cropSize,
}: {
  imageSize: { width: number; height: number };
  positionX: number;
  positionY: number;
  cropSize: number;
}) {
  const boundedCropSize = clamp(cropSize, 20, 100);
  const minSide = Math.min(imageSize.width, imageSize.height);
  const cropPixelSize = (boundedCropSize / 100) * minSide;
  const sourceX = clamp(
    (positionX / 100) * imageSize.width - cropPixelSize / 2,
    0,
    imageSize.width - cropPixelSize,
  );
  const sourceY = clamp(
    (positionY / 100) * imageSize.height - cropPixelSize / 2,
    0,
    imageSize.height - cropPixelSize,
  );

  return {
    left: `${-(sourceX / cropPixelSize) * 100}%`,
    top: `${-(sourceY / cropPixelSize) * 100}%`,
    width: `${(imageSize.width / cropPixelSize) * 100}%`,
    height: `${(imageSize.height / cropPixelSize) * 100}%`,
  };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}
