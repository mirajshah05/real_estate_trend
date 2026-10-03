import test from "node:test";
import assert from "node:assert/strict";
import { propertyPage, referenceFilters, roomBounds } from "./propertyResults.js";

test("reference home defaults to exact 2-bedroom, 1-bathroom matches", () => {
  const filters = referenceFilters({ property_type: "Single Family", beds: 2, baths: 1, sqft: 1000 });
  assert.deepEqual(roomBounds(filters), { min_beds: 2, max_beds: 2, min_baths: 1, max_baths: 1 });
  assert.equal(filters.min_sqft, 800);
  assert.equal(filters.max_sqft, 1200);
  assert.deepEqual(roomBounds({ ...filters, bed_match: "at_least" }), { min_beds: 2, max_beds: null, min_baths: 1, max_baths: 1 });
});

test("missing reference facts stay optional and a studio matches exactly zero bedrooms", () => {
  assert.deepEqual(roomBounds(referenceFilters({})), { min_beds: null, max_beds: null, min_baths: null, max_baths: null });
  assert.equal(roomBounds(referenceFilters({ beds: 0 })).max_beds, 0);
});

test("nearest sorts the whole sample before paging, without mutating it", () => {
  const rows = Array.from({ length: 23 }, (_, index) => ({ listing_id: String(index), distance_miles: 23 - index }));
  const original = [...rows];
  const first = propertyPage(rows);
  const second = propertyPage(rows, { page: 2 });
  const last = propertyPage(rows, { page: 99 });
  assert.deepEqual(first.rows.map(row => row.distance_miles), [1,2,3,4,5,6,7,8,9,10]);
  assert.equal(second.first, 11);
  assert.equal(second.last, 20);
  assert.equal(last.page, 3);
  assert.equal(last.rows.length, 3);
  assert.equal(new Set([...first.rows, ...second.rows, ...last.rows].map(row => row.listing_id)).size, 23);
  assert.deepEqual(rows, original);
});

test("price sorts use the complete sample and always put unknown prices last", () => {
  const rows = [{ listing_id: "unknown", price: null }, { listing_id: "cheap", price: 100 }, { listing_id: "expensive", price: 200 }, { listing_id: "invalid", price: NaN }];
  assert.deepEqual(propertyPage(rows, { sort: "price_desc" }).rows.map(row => row.listing_id), ["expensive", "cheap", "invalid", "unknown"]);
  assert.deepEqual(propertyPage(rows, { sort: "price_asc", pageSize: 1, page: 2 }).rows.map(row => row.listing_id), ["expensive"]);
});

test("sale sorting uses actual dates, with deterministic ties and an empty result page", () => {
  const rows = [{ event_id: "b", sale_date: "2026-01-01" }, { event_id: "a", sale_date: "2026-02-01" }, { event_id: "c", sale_date: "2026-02-01" }, { event_id: "unknown" }];
  assert.deepEqual(propertyPage(rows, { sort: "recent" }).rows.map(row => row.event_id), ["a", "c", "b", "unknown"]);
  const empty = propertyPage([], { page: 9 });
  assert.equal(empty.page, 1);
  assert.equal(empty.first, 0);
  assert.equal(empty.last, 0);
});
