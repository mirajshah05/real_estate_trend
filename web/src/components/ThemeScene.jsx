import { useTheme } from "../ThemeProvider.jsx";
import { HOUSES, SHIPS } from "../themes.js";

// Small local vectors keep the decorative scenes crisp without extra downloads.
export function Spacecraft({ ship = "falcon", className = "" }) {
  return <svg className={`spacecraft ${className}`} viewBox="0 0 240 150" aria-hidden="true" focusable="false">
    {ship === "falcon" ? <g stroke="#768ba2" strokeWidth="2" strokeLinejoin="round">
      <path className="engine-glow" d="M45 103 Q108 143 171 103" stroke="#77d5ff" strokeWidth="9" fill="none" />
      <ellipse cx="108" cy="83" rx="72" ry="48" fill="#c5d0d6" />
      <path d="M56 54 L61 10 L93 49 M116 43 L145 9 L158 58" fill="#d8e2e7" />
      <path d="M163 59 L207 45 L226 54 L184 84 L163 80" fill="#b7c5cf" />
      <path d="M200 48 L204 67 L222 55" fill="#35516a" />
      <ellipse cx="108" cy="79" rx="22" ry="17" fill="#a4b5bf" />
      <path d="M108 62 V39 M87 76 L48 66 M88 88 L54 106 M126 89 L157 109 M130 76 L169 66 M108 95 V124" fill="none" />
      <path d="M71 91 L91 96 L89 104 L70 99 M125 101 L143 96 L146 104 L128 110" fill="#657d8f" />
      <circle cx="102" cy="79" r="5" fill="#edf3f5" /><circle cx="128" cy="61" r="6" fill="#334858" />
      <path d="M63 38 L83 42 M133 38 L149 37 M51 85 L66 86 M149 85 L170 85" fill="none" />
    </g> : ship === "xwing" ? <g stroke="#778da1" strokeWidth="2" strokeLinejoin="round">
      <path d="M97 70 L24 28 L13 31 L86 88 L14 125 L28 132 L106 97 L143 97 L219 131 L230 124 L156 85 L229 30 L216 27 L144 70" fill="#b8c9d4" />
      <path d="M109 110 L110 47 L121 5 L133 46 L137 111 Z" fill="#e0e7eb" />
      <path d="M114 60 L121 40 L129 61 L127 82 L115 82 Z" fill="#3c607e" />
      {[62, 163].map(x => <g key={x}><rect x={x} y="56" width="15" height="48" rx="7" fill="#7f99ab" /><path className="engine-glow" d={`M${x + 7} 105 v18`} stroke="#93dfff" strokeWidth="9" /></g>)}
      <path d="M15 19 V46 M227 18 V45 M16 111 V138 M226 108 V137" stroke="#f5de8c" strokeWidth="3" />
      <path d="M35 40 L57 54 M187 53 L208 39 M39 120 L61 107 M185 109 L207 121" stroke="#b64d41" strokeWidth="5" />
    </g> : <g stroke="#516e8b" strokeWidth="2" strokeLinejoin="round">
      <path d="M66 95 L119 135 L176 96" stroke="#b9b0a1" fill="none" />
      <path d="M112 127 L105 145 L135 145 L128 127 Z" fill="#dfc28a" />
      <path d="M55 70 L184 70" stroke="#8fcfff" strokeWidth="5" className="engine-glow" />
      {[42, 160].map(x => <g key={x}><rect x={x} y="12" width="37" height="99" rx="17" fill="#c3d9e9" /><path d={`M${x} 44 h37 M${x} 68 h37 M${x + 9} 14 v94 M${x + 27} 14 v94`} stroke="#4b83b6" strokeWidth="5" /><ellipse cx={x + 18} cy="21" rx="14" ry="9" fill="#304b64" /><path className="engine-glow" d={`M${x + 18} 111 v20`} stroke="#8bdcfd" strokeWidth="11" /></g>)}
    </g>}
  </svg>;
}

function Stars({ count = 110 }) {
  return <svg className="scene-stars" viewBox="0 0 600 210" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
    {Array.from({ length: count }, (_, i) => <circle key={i} cx={(i * 137 + 17) % 600} cy={(i * 73 + 9) % 210} r={i % 9 === 0 ? 1.7 : .8} fill="#e3f0ff" opacity={.35 + (i % 5) * .14} />)}
  </svg>;
}
function Castle() {
  return <svg className="castle-art" viewBox="0 0 600 210" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
    <circle cx="479" cy="45" r="23" fill="#f6ddb1" opacity=".85" />
    <path d="M0 192 Q68 154 134 181 Q220 145 310 178 Q410 136 507 171 L600 154 V210 H0" fill="#23384b" />
    <g fill="#172438" stroke="#697685" strokeWidth="1">
      <path d="M133 198 V132 H156 V104 H178 V132 H221 V96 H246 V54 H266 V96 H309 V122 H337 V82 H359 V34 H382 V82 H409 V139 H438 V107 H461 V147 H488 V198 Z" />
      <path d="M149 105 L167 72 L185 105 Z M237 56 L256 15 L275 56 Z M350 36 L370 0 L390 36 Z M431 108 L450 79 L470 108 Z" fill="#1b2c43" />
      <path d="M190 135 L202 118 L215 135 M278 124 L291 102 L306 124 M391 140 L404 118 L418 140" />
      <path d="M236 198 V159 Q256 126 277 159 V198 M324 198 V164 Q337 146 350 164 V198" fill="#101a2c" />
      <path d="M107 198 V155 H120 V143 H137 V155 H150 V198 M468 198 V166 H481 V154 H495 V166 H508 V198" />
    </g>
    <g fill="#f4cd80">{[160,173,231,250,263,283,298,344,363,376,396,445,455,475,490].map((x,i) => <rect key={x} x={x} y={i % 3 === 0 ? 149 : i % 3 === 1 ? 123 : 102} width="4" height="9" rx="2" />)}</g>
    <path d="M126 200 Q308 174 505 201" fill="none" stroke="#8497a2" opacity=".35" />
  </svg>;
}
function Owl() {
  return <svg className="owl-art" viewBox="0 0 100 110" aria-hidden="true" focusable="false">
    <path d="M20 30 L18 9 L36 20 Q52 10 68 20 L83 9 L79 35 Q91 65 76 91 L25 91 Q9 63 20 30" fill="#d7c7a6" stroke="#8f7755" strokeWidth="2" />
    <path d="M23 50 Q6 72 24 92 L36 82 M76 50 Q94 73 76 93 L66 82" fill="#ab9674" />
    <circle cx="35" cy="39" r="17" fill="#f9efd7" /><circle cx="65" cy="39" r="17" fill="#f9efd7" />
    <circle cx="35" cy="39" r="7" fill="#b98a39" /><circle cx="65" cy="39" r="7" fill="#b98a39" />
    <circle cx="35" cy="38" r="4" fill="#242124" /><circle cx="65" cy="38" r="4" fill="#242124" />
    <path d="M44 51 L50 61 L56 51 Z" fill="#795328" /><path d="M36 69 l5 6 5-6 M49 78 l5 6 5-6 M61 66 l5 6 5-6" fill="none" stroke="#8f7755" />
    <rect x="22" y="86" width="57" height="23" rx="2" fill="#f7e8c6" stroke="#9c7b4c" /><path d="M24 87 L50 103 L77 87" fill="none" stroke="#9c7b4c" /><circle cx="50" cy="102" r="5" fill="var(--house-banner)" />
  </svg>;
}
function Neighborhood() {
  return <svg className="neighborhood-art" viewBox="0 0 600 210" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
    <g fill="#fff"><ellipse cx="85" cy="43" rx="48" ry="13" /><circle cx="79" cy="34" r="17" /><circle cx="97" cy="36" r="12" /><ellipse cx="442" cy="53" rx="64" ry="15" /><circle cx="430" cy="40" r="20" /><circle cx="461" cy="45" r="17" /></g>
    <path d="M0 188 Q190 143 360 178 Q490 154 600 174 V210 H0" fill="#99c95b" stroke="#33303a" strokeWidth="3" />
    {[{x:65,c:'#f3bbcb',r:'#9b6b88'}, {x:252,c:'#f0d888',r:'#bd7c63'}, {x:437,c:'#c5dce7',r:'#836b99'}].map(({x,c,r}) => <g key={x} stroke="#33303a" strokeWidth="3" strokeLinejoin="round"><path d={`M${x} 187 V118 L${x + 65} 76 L${x + 130} 118 V187 Z`} fill={c} /><path d={`M${x - 10} 122 L${x + 65} 72 L${x + 140} 122 L${x + 130} 133 L${x + 65} 91 L${x} 133 Z`} fill={r} /><rect x={x + 17} y="138" width="26" height="26" fill="#91d0ee" /><rect x={x + 86} y="138" width="26" height="26" fill="#91d0ee" /><path d={`M${x + 55} 187 V139 Q${x + 65} 128 ${x + 76} 139 V187`} fill="#956352" /><path d={`M${x + 30} 138 V164 M${x + 17} 151 H${x + 43} M${x + 99} 138 V164 M${x + 86} 151 H${x + 112}`} /></g>)}
    <path d="M294 210 L316 185 L339 185 L364 210" fill="#e5d8b9" />
  </svg>;
}
export default function ThemeScene() {
  const { theme, appearance } = useTheme();
  if (theme.id === "default" || !appearance.atmosphere) return null;
  if (theme.id === "galactic") return <div className="theme-scene galactic-scene" data-testid="galactic-scene"><Stars /><div className="scene-orbit" /><div className="scene-ship"><Spacecraft ship={appearance.ship} /></div><span className="scene-caption">{SHIPS[appearance.ship]} · Galactic Console</span><span className="scene-coordinate" aria-hidden="true">✦ &nbsp; SECTOR: HOME</span></div>;
  if (theme.id === "enchanted") return <div className="theme-scene enchanted-scene" data-testid="enchanted-scene"><Stars count={70} /><Castle /><div className="floating-candles" aria-hidden="true">{[9,22,38,55,72,86].map((left,i) => <span className="candle" key={left} style={{left:`${left}%`,top:`${20 + (i % 3) * 18}px`,animationDelay:`-${i * 1.7}s`}}><i /></span>)}</div><div className="house-banner"><span aria-hidden="true">✧</span><strong>{HOUSES[appearance.house].label}</strong><small>{HOUSES[appearance.house].animal}</small></div><Owl /><span className="scene-caption">The Enchanted Atlas · a new chapter</span></div>;
  if (theme.id === "springfield") return <div className="theme-scene springfield-scene" data-testid="springfield-scene"><Neighborhood /><div className="scene-donut" aria-hidden="true" /><span className="scene-caption">Springfield Living · hello, neighbor!</span></div>;
  return <div className="theme-scene dialup-scene" data-testid="dialup-scene"><div className="retro-title"><span aria-hidden="true">▣</span> REALTYKIT BHARAT ONLINE <span aria-hidden="true">_ □ ×</span></div><div className="retro-location">Location: <span>RealtyKit / Property Research</span></div><div className="retro-welcome">NAMASTE &amp; WELCOME TO CYBER BHARAT!</div><div className="retro-bulletin">LATEST BULLETIN · Homes · Rents · Market trends</div><div className="retro-status">Document: Ready <span>Dial-up India ’99</span></div></div>;
}
export function LoadingShip() {
  const { theme, appearance } = useTheme();
  if (theme.id !== "galactic" || !appearance.atmosphere) return null;
  return <span className="loading-ship"><Spacecraft ship="podracer" /></span>;
}
