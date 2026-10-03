export const APPEARANCE_KEY = "realtykit.appearance.v1";
export const DEFAULT_APPEARANCE = Object.freeze({ theme: "default", house: "ravenclaw", ship: "falcon", atmosphere: true, motion: true });
export const HOUSES = {
  gryffindor: { label: "Gryffindor", accent: "#8c2631", banner: "#8c2631", trim: "#e4be63", animal: "Lion" },
  ravenclaw: { label: "Ravenclaw", accent: "#245471", banner: "#173e5b", trim: "#dab274", animal: "Eagle" },
  slytherin: { label: "Slytherin", accent: "#24614b", banner: "#184737", trim: "#d2ded5", animal: "Serpent" },
  hufflepuff: { label: "Hufflepuff", accent: "#755515", banner: "#533f1f", trim: "#f4ce5c", animal: "Badger" },
};
export const SHIPS = { falcon: "Millennium Falcon", xwing: "X-wing", podracer: "Podracer" };

const base = {
  bg: "#0f0f1a", panel: "#16162a", accent: "#4361ee", "on-accent": "#ffffff",
  text: "#e8e8f0", muted: "#a2a2b7", line: "#34344e", link: "#a4b2ff",
  live: "#71cda2", fresh: "#90a2ff", aging: "#e5a260", stale: "#dfbf5e", unavail: "#a2a2b7",
  down: "#ed8f82", halo: "#e9c46a", positive: "#4361ee", "positive-soft": "#3d5a80",
  negative: "#c44536", "negative-soft": "#8b5a4a", neutral: "#6b6b80", selected: "#ffffff",
  boundary: "#49c6b3", listing: "#e8e8f0", "map-bg": "#0b0b14",
  "series-1": "#8197ff", "series-2": "#e8e8f0", "series-3": "#e9c46a", "series-4": "#6dd6c0",
  font: '"IBM Plex Sans", "Segoe UI", system-ui, sans-serif',
  "title-font": '"IBM Plex Sans", "Segoe UI", system-ui, sans-serif',
  mono: '"IBM Plex Mono", "SF Mono", ui-monospace, Menlo, monospace',
};
const light = {
  "on-accent": "#ffffff", text: "#302b28", muted: "#665e53", line: "#c2b9a5",
  live: "#24654b", fresh: "#2459ac", aging: "#8c491a", stale: "#7b5911", unavail: "#68645b",
  down: "#aa3528", halo: "#97640a", positive: "#3157cb", "positive-soft": "#6586bf",
  negative: "#ba382b", "negative-soft": "#cf8171", neutral: "#87837e", selected: "#241c16",
  boundary: "#187966", listing: "#514162", "map-bg": "#e9e6df",
  "series-1": "#3157b7", "series-2": "#72447d", "series-3": "#97620e", "series-4": "#187966",
};
export const THEMES = [
  { id: "default", name: "Original", subtitle: "The classic dark dashboard", scene: "Research your next move", scheme: "dark", tiles: "dark_all", tokens: {} },
  { id: "galactic", name: "Dark Side", subtitle: "Galactic Console", scene: "Chart your next move", scheme: "dark", tiles: "dark_all", tokens: {
    bg: "#08111f", panel: "#101e30", accent: "#f4d574", "on-accent": "#151c27", text: "#eaf4ff", muted: "#a9bfd5", line: "#344b65", link: "#f4d574",
    font: '"Segoe UI", system-ui, sans-serif', "title-font": '"Segoe UI", system-ui, sans-serif',
  } },
  { id: "enchanted", name: "Potter head", subtitle: "Enchanted Atlas", scene: "Find where you belong", scheme: "light", tiles: "light_all", tokens: {
    ...light, bg: "#ece0c8", panel: "#f8efd9", accent: "#245471", link: "#245471", line: "#c8b594", "title-font": 'Georgia, "Times New Roman", serif',
  } },
  { id: "springfield", name: "Satirical", subtitle: "Springfield Living", scene: "A place to call home", scheme: "light", tiles: "light_all", tokens: {
    ...light, bg: "#e8f5fb", panel: "#fff8df", accent: "#87215d", link: "#87215d", text: "#2f2532", muted: "#605160", line: "#574b5a", "title-font": '"Trebuchet MS", "Segoe UI", sans-serif',
  } },
  { id: "dialup", name: "90s Internet", subtitle: "Dial-up India ’99", scene: "Namaste, house hunter!", scheme: "light", tiles: "light_all", tokens: {
    ...light, bg: "#e9e7de", panel: "#f6f5ed", accent: "#000080", link: "#000080", text: "#171717", muted: "#52524b", line: "#939389",
    "title-font": 'Georgia, "Times New Roman", serif', font: 'Arial, Helvetica, sans-serif', mono: '"Courier New", monospace',
  } },
];

export function normalizeAppearance(value) {
  const input = value && typeof value === "object" ? value : {};
  return {
    theme: THEMES.some(theme => theme.id === input.theme) ? input.theme : DEFAULT_APPEARANCE.theme,
    house: Object.hasOwn(HOUSES, input.house) ? input.house : DEFAULT_APPEARANCE.house,
    ship: Object.hasOwn(SHIPS, input.ship) ? input.ship : DEFAULT_APPEARANCE.ship,
    atmosphere: typeof input.atmosphere === "boolean" ? input.atmosphere : DEFAULT_APPEARANCE.atmosphere,
    motion: typeof input.motion === "boolean" ? input.motion : DEFAULT_APPEARANCE.motion,
  };
}
export function readAppearance(storage) {
  try { return normalizeAppearance(JSON.parse(storage.getItem(APPEARANCE_KEY))); }
  catch { return { ...DEFAULT_APPEARANCE }; }
}
export function saveAppearance(storage, value) {
  try { storage.setItem(APPEARANCE_KEY, JSON.stringify(normalizeAppearance(value))); return true; }
  catch { return false; }
}
export function resolveTheme(value) {
  const appearance = normalizeAppearance(value);
  const theme = THEMES.find(item => item.id === appearance.theme);
  const tokens = { ...base, ...theme.tokens };
  const house = HOUSES[appearance.house];
  if (theme.id === "enchanted") { tokens.accent = house.accent; tokens.link = house.accent; }
  tokens["house-banner"] = house.banner;
  tokens["house-trim"] = house.trim;
  return { ...theme, tokens, appearance };
}
export function applyAppearance(element, value, reducedMotion = false) {
  const theme = resolveTheme(value);
  element.dataset.theme = theme.id;
  element.dataset.atmosphere = String(theme.appearance.atmosphere);
  element.dataset.motion = String(theme.appearance.motion && !reducedMotion);
  element.style.colorScheme = theme.scheme;
  for (const [key, token] of Object.entries(theme.tokens)) element.style.setProperty(`--${key}`, token);
}
export function chartPalette(theme) {
  const t = theme.tokens;
  return {
    axis: { stroke: t.muted, fill: t.muted, fontSize: 11 }, grid: { stroke: t.line },
    tip: { background: t.panel, color: t.text, border: `1px solid ${t.line}` },
    housing: t["series-1"], gspc: t["series-2"], mortgage: t["series-3"],
    bedrooms: { 1: t["series-4"], 2: t["series-1"], 3: t["series-3"] },
  };
}
export function marketColor(value, maxAbs, tokens) {
  if (value == null || !Number.isFinite(value) || !maxAbs) return tokens.neutral;
  const fraction = Math.max(-1, Math.min(1, value / maxAbs));
  if (fraction < 0) return fraction < -0.5 ? tokens.negative : tokens["negative-soft"];
  if (fraction > 0.5) return tokens.positive;
  return fraction > 0 ? tokens["positive-soft"] : tokens.neutral;
}
export function tileUrl(theme, key = "") {
  return `https://{s}.basemaps.cartocdn.com/${theme.tiles}/{z}/{x}/{y}{r}.png` + (key ? `?key=${encodeURIComponent(key)}` : "");
}
