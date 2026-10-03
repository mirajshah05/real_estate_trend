import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { applyAppearance, chartPalette, normalizeAppearance, readAppearance, resolveTheme, saveAppearance } from "./themes.js";

const ThemeContext = createContext(null);
export function bootstrapAppearance() {
  let storage;
  try { storage = window.localStorage; } catch { /* Private browsers can disable storage. */ }
  const appearance = readAppearance(storage);
  applyAppearance(document.documentElement, appearance, window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  return appearance;
}
export default function ThemeProvider({ children, initialAppearance }) {
  const [appearance, setAppearance] = useState(() => normalizeAppearance(initialAppearance));
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [saved, setSaved] = useState(true);
  const theme = useMemo(() => resolveTheme(appearance), [appearance]);
  const palette = useMemo(() => chartPalette(theme), [theme]);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useLayoutEffect(() => { applyAppearance(document.documentElement, appearance, reducedMotion); }, [appearance, reducedMotion]);
  const updateAppearance = (patch) => {
    setAppearance(previous => normalizeAppearance({ ...previous, ...patch }));
  };
  useEffect(() => {
    try { setSaved(saveAppearance(window.localStorage, appearance)); }
    catch { setSaved(false); }
  }, [appearance]);
  return <ThemeContext.Provider value={{ theme, appearance, updateAppearance, palette, saved, reducedMotion, motion: appearance.motion && !reducedMotion }}>{children}</ThemeContext.Provider>;
}
export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme requires ThemeProvider");
  return context;
}
