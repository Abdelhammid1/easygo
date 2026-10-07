import { useEffect, useState } from "react";
import { IconMoon, IconSun } from "../icons";

type Mode = "light" | "dark" | "system";

function apply(mode: Mode) {
  const root = document.documentElement;
  if (mode === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", mode);
}

function systemDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeToggle() {
  const [mode, setMode] = useState<Mode>(() => {
    try {
      return (localStorage.getItem("theme") as Mode) || "system";
    } catch {
      return "system";
    }
  });

  useEffect(() => {
    apply(mode);
    try {
      localStorage.setItem("theme", mode);
    } catch {
      /* ignore */
    }
  }, [mode]);

  const isDark = mode === "dark" || (mode === "system" && systemDark());

  return (
    <button className="iconbtn" title="تبديل السمة" aria-label="تبديل السمة"
      onClick={() => setMode(isDark ? "light" : "dark")}>
      {isDark ? <IconSun /> : <IconMoon />}
    </button>
  );
}
