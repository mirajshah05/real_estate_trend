import { sourcesPanelRows } from "../normalize.js";

const LINKS = {
  zillow: { href: "https://www.zillow.com/research/data/", label: "Zillow Research" },
  redfin: { href: "https://www.redfin.com/news/data-center/", label: "Redfin Data Center" },
  compass: { href: null, label: "Compass" },
  yahoo: { href: "https://finance.yahoo.com/quote/%5EGSPC", label: "Yahoo Finance" },
  fred: { href: "https://fred.stlouisfed.org/series/MORTGAGE30US", label: "FRED MORTGAGE30US" },
  government: {
    href: "https://services2.arcgis.com/tcv2cMrq63AgvbHF/arcgis/rest/services/Parcels_Public_View/FeatureServer/0",
    label: "Santa Clara / San Mateo county GIS",
  },
};

const NOTES = {
  zillow: "Weekly inventory / DOM / new listings. File date is not the observation week.",
  redfin: "National tracker is historical. S3 last moved 2026-06; treat as stale.",
  compass: "No official public API. Adapter stays unavailable. Not scraped.",
  yahoo: "^GSPC / ^IXIC via chart API, isolated on the server.",
  fred: "30-year mortgage. Uses the configured official FRED API key first, with public CSV/PMMS fallbacks.",
  government: "Free official boundary and parcel-reference layers. Dated snapshots live under resources/government; no sale prices.",
};

const GOVERNMENT_DATA = [
  ["FHFA HPI", "https://www.fhfa.gov/data/hpi/datasets"],
  ["Freddie Mac PMMS", "https://www.freddiemac.com/pmms/pmms_archives"],
  ["Census New Residential Sales", "https://www.census.gov/construction/nrs/data/series.html"],
  ["HMDA Data Browser", "https://ffiec.cfpb.gov/data-publication"],
  ["Santa Clara public parcels", "https://services2.arcgis.com/tcv2cMrq63AgvbHF/arcgis/rest/services/Parcels_Public_View/FeatureServer/0"],
  ["San Mateo GIS downloads", "https://www.smcgov.org/tsd/gis-data-download"],
];

export default function SourcesPanel({ freshness }) {
  const rows = sourcesPanelRows(freshness);

  return (
    <div className="sources-list">
      {rows.map((row) => {
        const link = LINKS[row.id];
        return (
          <div className="source-row" key={row.id}>
            <span className={`dot chip status-${row.status}`} style={{ border: 0, padding: 0 }}>
              <span className="dot" />
            </span>
            <div>
              <div>
                {link && link.href ? (
                  <a href={link.href} target="_blank" rel="noopener noreferrer">
                    {link.label}
                  </a>
                ) : (
                  link.label
                )}
                {" · "}
                {row.status}
              </div>
              <div className="meta">
                {row.as_of ? `observation ${row.as_of}` : "no observation"}
                {row.file_date ? ` · file ${row.file_date}` : ""}
              </div>
              <div className="meta">{row.note || NOTES[row.id]}</div>
            </div>
          </div>
        );
      })}
      <div className="source-research">
        <div className="source-research-title">Government data roadmap</div>
        <div className="meta">Official supplements for historical price, new-home sales, and mortgage context:</div>
        <div className="source-links">
          {GOVERNMENT_DATA.map(([label, href]) => (
            <a key={href} href={href} target="_blank" rel="noopener noreferrer">{label}</a>
          ))}
        </div>
        <div className="meta">Actual deed sale prices are jurisdiction-specific assessor/recorder feeds; there is no single nationwide federal parcel feed.</div>
      </div>
    </div>
  );
}
