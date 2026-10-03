import test from "node:test";
import assert from "node:assert/strict";
import { APPEARANCE_KEY, DEFAULT_APPEARANCE, THEMES, HOUSES, applyAppearance, chartPalette, marketColor, normalizeAppearance, readAppearance, resolveTheme, saveAppearance, tileUrl } from "./themes.js";
import { buildOverlayModel } from "./chartModels.js";

test("invalid saved preferences safely recover without accepting inherited option names", () => {
  assert.deepEqual(normalizeAppearance({ theme:"unknown", house:"__proto__", ship:"constructor", motion:"false", atmosphere:0 }), DEFAULT_APPEARANCE);
  assert.deepEqual(readAppearance({ getItem:() => "{broken json" }), DEFAULT_APPEARANCE);
  assert.deepEqual(readAppearance({ getItem:() => { throw new Error("blocked"); } }), DEFAULT_APPEARANCE);
});
test("all theme choices and custom options survive a storage round trip", () => {
  const records = new Map();
  const storage = { getItem:key => records.get(key), setItem:(key,value) => records.set(key,value) };
  for (const theme of THEMES) {
    const selection = { theme:theme.id, house:"slytherin", ship:"xwing", atmosphere:false, motion:false };
    assert.equal(saveAppearance(storage, selection), true);
    assert.deepEqual(readAppearance(storage), selection);
  }
  assert.ok(records.has(APPEARANCE_KEY));
  assert.equal(saveAppearance({ setItem:() => { throw new Error("quota"); } }, DEFAULT_APPEARANCE), false);
});
test("theme changes preserve market direction, neutral values and strong-change thresholds", () => {
  for (const definition of THEMES) {
    const { tokens } = resolveTheme({ theme:definition.id });
    assert.equal(marketColor(-10,10,tokens), tokens.negative);
    assert.equal(marketColor(-2,10,tokens), tokens["negative-soft"]);
    assert.equal(marketColor(10,10,tokens), tokens.positive);
    assert.equal(marketColor(2,10,tokens), tokens["positive-soft"]);
    for (const value of [null,0,NaN]) assert.equal(marketColor(value,10,tokens), tokens.neutral);
    assert.equal(marketColor(5,0,tokens), tokens.neutral);
    assert.notEqual(tokens.selected, tokens.positive);
  }
});
test("light and dark tiles use the same coordinates and encode optional credentials", () => {
  for (const definition of THEMES) {
    const theme = resolveTheme({ theme:definition.id });
    assert.ok(tileUrl(theme).includes(`/${theme.scheme === "dark" ? "dark_all" : "light_all"}/{z}/{x}/{y}{r}.png`));
    assert.ok(!tileUrl(theme).includes("?"));
    assert.ok(tileUrl(theme,"a&b").endsWith("?key=a%26b"));
  }
});
test("overlay themes change presentation while preserving values, units and shared dates", () => {
  const series = { zhvi:[{t:"2026-01-01",v:100},{t:"2026-02-01",v:120}], gspc:[{t:"2026-01-01",v:10},{t:"2026-02-01",v:20}], mortgage_30y:[{t:"2026-01-01",v:6},{t:"2026-02-01",v:5}] };
  const original = buildOverlayModel(series);
  for (const theme of THEMES) {
    const colors = chartPalette(resolveTheme({theme:theme.id}));
    const model = buildOverlayModel(series,colors);
    assert.deepEqual(model.rows, original.rows);
    assert.equal(model.from, original.from);
    assert.equal(model.to, original.to);
    for (const definition of model.definitions) {
      assert.equal(definition.color, colors[definition.key]);
      assert.equal(model.rawByKey[definition.key].color, definition.color);
      assert.deepEqual(definition.points, original.rawByKey[definition.key].points);
      assert.equal(definition.kind, original.rawByKey[definition.key].kind);
    }
  }
});
test("system reduced motion overrides saved motion without discarding the preference", () => {
  const element = { dataset:{}, style:{ setProperty() {} } };
  const value = { ...DEFAULT_APPEARANCE, theme:"galactic", motion:true };
  applyAppearance(element,value,true);
  assert.equal(element.dataset.motion,"false");
  applyAppearance(element,value,false);
  assert.equal(element.dataset.motion,"true");
  assert.equal(value.motion,true);
});
function luminance(hex) {
  const rgb = hex.slice(1).match(/../g).map(value => parseInt(value,16) / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
  return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
}
function contrast(a,b) {
  const first = luminance(a), second = luminance(b);
  return (Math.max(first,second) + .05) / (Math.min(first,second) + .05);
}
test("body, supporting text, links and primary actions meet 4.5:1 contrast in every house and theme", () => {
  for (const theme of THEMES) for (const house of Object.keys(HOUSES)) {
    const { tokens:t } = resolveTheme({theme:theme.id,house});
    for (const background of [t.bg,t.panel]) for (const foreground of [t.text,t.muted,t.link]) {
      assert.ok(contrast(foreground,background) >= 4.5, `${theme.id}/${house}: ${foreground} on ${background} = ${contrast(foreground,background).toFixed(2)}`);
    }
    assert.ok(contrast(t["on-accent"],t.accent) >= 4.5, `${theme.id}/${house}: primary action`);
  }
});
