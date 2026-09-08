import assert from "node:assert/strict";
import test from "node:test";

import {
  buildOverlayModel,
  buildRentalChartRows,
  monthKeysBetween,
  paddedMoneyDomain,
  rentalPointRadius,
  rentalSeasonality,
  selectCityMarketIndex,
} from "./chartModels.js";

test("rent axes focus on observed variation instead of starting at zero", () => {
  const [low, high] = paddedMoneyDomain([3520, 3610, 3740]);
  assert.ok(low > 0);
  assert.ok(low < 3520);
  assert.ok(high > 3740);
  assert.ok(high - low < 1000);
});

test("36-month history creates 36 calendar slots", () => {
  const months = monthKeysBetween("2023-08-01", "2026-07-31");
  assert.equal(months.length, 36);
  assert.equal(months[0], "2023-08");
  assert.equal(months.at(-1), "2026-07");
});

test("a one-month bedroom sample remains visible and available to the detail table", () => {
  const rows = buildRentalChartRows({
    rows: [
      { month: "2026-07", bedrooms: 1, property_type: "apartment", listing_status: "new", average_rent: 2700, median_rent: 2700, count: 3 },
      { month: "2026-07", bedrooms: 2, property_type: "apartment", listing_status: "new", average_rent: 3300, median_rent: 3300, count: 2 },
    ],
    dateFrom: "2026-06-01",
    dateTo: "2026-07-31",
    propertyType: "All",
    listingStatus: "All",
  });
  const observed = rows.filter((row) => row.bed1 != null || row.bed2 != null || row.bed3 != null);
  assert.deepEqual(observed, [{ month: "2026-07", bed1: 2700, count1: 3, bed2: 3300, count2: 2 }]);
  assert.equal(rentalPointRadius(rows), 4);
});

test("the rental benchmark must match the selected city", () => {
  const indices = [
    { city: "San Jose", points: [{ month: "2026-07", value: 3500 }] },
    { city: "Sunnyvale", points: [{ month: "2026-07", value: 3900 }] },
  ];
  assert.equal(selectCityMarketIndex(indices, "Sunnyvale").city, "Sunnyvale");
  assert.equal(selectCityMarketIndex(indices, "Palo Alto"), null);
});

test("seasonality compares matching summer months and complete years", () => {
  const points = [];
  for (const year of [2024, 2025]) {
    for (let month = 1; month <= 12; month += 1) {
      points.push({ month: `${year}-${String(month).padStart(2, "0")}`, value: 3000 + month * 10 + (year - 2024) * 100 });
    }
  }
  points.push({ month: "2026-06", value: 3400 }, { month: "2026-07", value: 3500 });
  const result = rentalSeasonality(points);
  assert.deepEqual(result.summer.months, [6, 7]);
  assert.equal(result.summer.partial, true);
  assert.equal(result.peak.month, 12);
  assert.deepEqual(result.yearsAnalyzed, [2024, 2025]);
});

test("overlay model renders both housing and stocks over a shared window", () => {
  const model = buildOverlayModel({
    zhvi: [
      { t: "2024-01-31", v: 700000 },
      { t: "2024-02-29", v: 710000 },
      { t: "2024-03-31", v: 720000 },
    ],
    gspc: [
      { t: "2024-01-15", v: 4700 },
      { t: "2024-02-15", v: 4900 },
      { t: "2024-03-15", v: 5100 },
      { t: "2024-04-15", v: 5000 },
    ],
  });
  assert.deepEqual(model.definitions.map((item) => item.key), ["housing", "gspc"]);
  assert.equal(model.from, "2024-01-31");
  assert.equal(model.to, "2024-03-31");
  assert.ok(model.rows.some((row) => Number.isFinite(row.housing)));
  assert.ok(model.rows.some((row) => Number.isFinite(row.gspc)));
});
