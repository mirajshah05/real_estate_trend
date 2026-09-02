# Government resource snapshots

Government downloads are stored by UTC refresh date:

```text
resources/
  government/
    YYYY-MM-DD/
      manifest.json
      santa-clara/
        city-limits.layer.json
        target-city-boundaries.geojson
        parcels.layer.json
        parcel-counts/
      san-mateo/
        active-parcels.service.json
```

`manifest.json` records the source URL, fetch timestamp, HTTP metadata, SHA-256,
file size, geographic scope, and limitations for every downloaded object.

The Santa Clara snapshot covers Palo Alto, Santa Clara, Mountain View,
Sunnyvale, and San Jose. San Mateo is retained as an adjacent free reference
source, but it does not cover those five cities. These GIS files provide
boundaries and parcel-reference data, not verified deed sale prices.

Run only this refresh with:

```bash
realtykit ingest refresh --providers government
```

Repeated refreshes on the same UTC date reuse the same dated folder and HTTP
cache validators. A later date creates a new snapshot without overwriting the
prior date.
