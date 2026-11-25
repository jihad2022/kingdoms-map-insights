# Kingdoms Map Insights

Explore Travian Kingdoms external API snapshots with Python 3.9 or later. Use
the command directly from this directory. It has no third-party dependencies.

```sh
python3 kingdoms_map_insights.py --snapshot map.json statistics
python3 kingdoms_map_insights.py --snapshot map.json croppers --crop 15 --center -52 -8 --radius 15 --unoccupied --format csv
python3 kingdoms_map_insights.py --snapshot map.json oases --center 0 0 --radius 10
python3 kingdoms_map_insights.py --world com1nx3 --date 2026-11-20 statistics
```

For network requests, supply your own authorized private API key as
`KINGDOMS_API_KEY` through your local secret manager or shell environment.
Dated requests reuse the local cache. JSON input is the external API response
envelope. Keep snapshot files local if they include player authentication
tokens. Fetched snapshots remove the documented external login token before
caching.

The proximity filter uses straight-line geometric distance in map coordinates.
The occupancy filter checks the snapshot's player village lists. Check current
settlement eligibility in-game. Oasis results include the external API oasis
type code.

Schema references: [external API documentation](https://wiki.binary-tools.de/wiki/Kingdoms_API/en)
and [reference client](https://github.com/JaLe29/travian-kingdoms-api).

Run the test suite with `python3 -m unittest`.
