import React from "react";
import Link from "next/link";

interface Props {
  image?: string | null;
  name?: string | null;
  href?: string | null;
}

//generate a bg color for Avatar
function stringToColor(str?: string | null) {
  if (!str) return "#bbb";
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }

  const h = Math.abs(hash) % 360;
  const s = 55;
  const l = 68;
  return `hsl(${h}, ${s}%, ${l}%)`;
}

function getInitials(name?: string | null) {
  if (!name) return "?";
  const words = name.trim().split(" ");
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

export default function Avatar({ image, name, href }: Props) {
  const initials = getInitials(name);
  const bgColor = stringToColor(name);

  return href ? (
    <Link href={href} className="flex items-center">
      {image && image.trim() !== "" ? (
        <img
          src={image}
          alt={name || "avatar"}
          className="w-8 h-8 rounded-full border border-foreground/20 hover:border-foreground transition object-cover"
        />
      ) : (
        <div
          className="w-8 h-8 flex items-center justify-center rounded-full bg-muted text-foreground font-bold border border-foreground/20 hover:border-foreground transition select-none"
          style={{ backgroundColor: bgColor }}
        >
          {initials}
        </div>
      )}
    </Link>
  ) : null;
}
