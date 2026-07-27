"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

const APP_SCROLL_CONTAINER_ID = "app-scroll-container";

export function ScrollToTop() {
  const pathname = usePathname();

  useEffect(() => {
    const scrollContainer = document.getElementById(
      APP_SCROLL_CONTAINER_ID,
    );

    scrollContainer?.scrollTo({ top: 0, left: 0, behavior: "auto" });
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [pathname]);

  return null;
}

export { APP_SCROLL_CONTAINER_ID };
