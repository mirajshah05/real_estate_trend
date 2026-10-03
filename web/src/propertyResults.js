// Sort the complete retrieved sample before selecting a display page.
// Unknown values sort last; stable identity resolves ties across pages.
const present = value => typeof value === "number" && Number.isFinite(value);

function numericCompare(a, b, direction = 1) {
  if (!present(a)) return present(b) ? 1 : 0;
  if (!present(b)) return -1;
  return (a - b) * direction;
}

export function propertyPage(rows, { sort = "nearest", page = 1, pageSize = 10 } = {}) {
  const ordered = [...rows].sort((a, b) => {
    let comparison;
    if (sort === "price_asc" || sort === "price_desc") {
      comparison = numericCompare(a.price, b.price, sort === "price_desc" ? -1 : 1);
    } else if (sort === "recent") {
      comparison = (b.sale_date || "").localeCompare(a.sale_date || "");
    } else {
      comparison = numericCompare(a.distance_miles, b.distance_miles);
    }
    return comparison || numericCompare(a.distance_miles, b.distance_miles)
      || String(a.listing_id || a.event_id || "").localeCompare(String(b.listing_id || b.event_id || ""));
  });
  const size = Math.max(1, Math.floor(Number(pageSize) || 10));
  const pages = Math.max(1, Math.ceil(ordered.length / size));
  const current = Math.max(1, Math.min(pages, Math.floor(Number(page) || 1)));
  const start = (current - 1) * size;
  return { rows: ordered.slice(start, start + size), page: current, pages, total: rows.length,
    first: rows.length ? start + 1 : 0, last: Math.min(start + size, rows.length) };
}

export function referenceFilters(property) {
  return { property_type: property.property_type || "", min_beds: property.beds ?? "",
    min_baths: property.baths ?? "", bed_match: "exact", bath_match: "exact",
    min_sqft: property.sqft ? Math.floor(property.sqft * 0.8) : "",
    max_sqft: property.sqft ? Math.ceil(property.sqft * 1.2) : "" };
}

export function roomBounds(filters) {
  const beds = filters.min_beds === "" ? null : Number(filters.min_beds);
  const baths = filters.min_baths === "" ? null : Number(filters.min_baths);
  return { min_beds: beds, max_beds: filters.bed_match === "exact" ? beds : null,
    min_baths: baths, max_baths: filters.bath_match === "exact" ? baths : null };
}
