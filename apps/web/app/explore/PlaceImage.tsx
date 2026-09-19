"use client";

import { useState } from "react";
import { gradientFor } from "./gradient";

/**
 * Place imagery with graceful degradation: tries
 * /images/places/{slug}/{kind}.jpg and falls back to a deterministic
 * two-tone gradient derived from the slug when no photo exists yet.
 * (Real photography is dropped into public/images/places/{slug}/ as it
 * becomes available — no code change needed.)
 */

export default function PlaceImage({
  slug,
  kind = "hero",
  alt,
  className,
  sizes,
  priority,
}: {
  slug: string;
  kind?: "hero" | "about" | `gallery-${number}`;
  alt: string;
  className?: string;
  sizes?: string;
  priority?: boolean;
}) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        aria-label={alt}
        role="img"
        className={className}
        style={{ background: gradientFor(slug) }}
      />
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- dynamic optional asset; optimizer 404s are handled via onError
    <img
      src={`${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/images/places/${slug}/${kind}.jpg`}
      alt={alt}
      sizes={sizes}
      loading={priority ? "eager" : "lazy"}
      onError={() => setFailed(true)}
      className={className}
    />
  );
}
