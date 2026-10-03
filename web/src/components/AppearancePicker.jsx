import { useEffect, useRef, useState } from "react";
import { useTheme } from "../ThemeProvider.jsx";
import { DEFAULT_APPEARANCE, HOUSES, SHIPS, THEMES } from "../themes.js";

export default function AppearancePicker() {
  const { appearance, updateAppearance, reducedMotion, saved } = useTheme();
  const [open, setOpen] = useState(false);
  const dialog = useRef(null);
  useEffect(() => {
    if (open && !dialog.current.open) dialog.current.showModal();
    if (!open && dialog.current.open) dialog.current.close();
  }, [open]);
  return <>
    <button type="button" className="appearance-trigger" onClick={() => setOpen(true)} aria-haspopup="dialog">Appearance</button>
    <dialog ref={dialog} className="appearance-dialog" aria-labelledby="appearance-title" onCancel={() => setOpen(false)} onClose={() => setOpen(false)}>
      <div className="appearance-heading"><div><span className="eyebrow">Make yourself at home</span><h2 id="appearance-title">Choose your world</h2></div><button type="button" onClick={() => setOpen(false)} aria-label="Close appearance">✕</button></div>
      <p className="panel-caption">Your research, dressed your way. Changes apply immediately.</p>
      <div className="appearance-presets" role="group" aria-label="Themes">
        {THEMES.map(theme => <button type="button" key={theme.id} className={`appearance-preset preset-${theme.id}`} aria-pressed={appearance.theme === theme.id} onClick={() => updateAppearance({ theme: theme.id })}>
          <span className="preset-preview" aria-hidden="true"><span className="preset-art">{({ default: "◉", galactic: "✦", enchanted: "✧", springfield: "☁", dialup: "▣" })[theme.id]}</span><span className="preset-preview-lines"><i /><i /><i /></span></span>
          <span className="preset-name">{theme.name}<span aria-hidden="true">{appearance.theme === theme.id ? "✓" : ""}</span></span><span className="preset-subtitle">{theme.subtitle}</span>
        </button>)}
      </div>
      <div className="appearance-options">
        {appearance.theme === "enchanted" && <label className="field"><span>Hogwarts house</span><select value={appearance.house} onChange={event => updateAppearance({ house: event.target.value })}>{Object.entries(HOUSES).map(([id, house]) => <option value={id} key={id}>{house.label}</option>)}</select></label>}
        {appearance.theme === "galactic" && <label className="field"><span>Your ship</span><select value={appearance.ship} onChange={event => updateAppearance({ ship: event.target.value })}>{Object.entries(SHIPS).map(([id, ship]) => <option value={id} key={id}>{ship}</option>)}</select></label>}
        <label className="appearance-toggle"><input type="checkbox" checked={appearance.atmosphere} onChange={event => updateAppearance({ atmosphere: event.target.checked })} /><span>Atmosphere<small>Ships, candles, clouds and retro textures</small></span></label>
        <label className="appearance-toggle"><input type="checkbox" checked={appearance.motion} onChange={event => updateAppearance({ motion: event.target.checked })} /><span>Ambient motion<small>{reducedMotion ? "Paused by your system’s reduced-motion setting" : "Gentle stars, candlelight and ship movement"}</small></span></label>
      </div>
      <div className="appearance-footer"><span role="status">{saved ? "Saved on this device" : "Applied for this visit · browser storage unavailable"}</span><div><button type="button" onClick={() => updateAppearance(DEFAULT_APPEARANCE)}>Reset</button><button type="button" className="primary-action" onClick={() => setOpen(false)}>Done</button></div></div>
    </dialog>
  </>;
}
