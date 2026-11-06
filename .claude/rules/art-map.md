---
paths:
  - "artsearch/templates/map.html"
  - "artsearch/management/commands/generate_art_map.py"
  - "artsearch/views/views.py"
---

# Art Map

`/map/` (`map.html`, deck.gl) plots every artwork at precomputed UMAP coordinates of its `image_jina` vector, made offline by `make art-map` (`generate_art_map`) and stored in `ArtMapData` (binary geometry plus metadata JSON, served at `/map/data/...`).

## Linking in and out

- Clicking a dot opens a panel linking to the artwork page and to Find similar (`/?query=<slug>:<object_number>`).
- "Show on map" on artwork pages and in the search popup links to `/map/?artwork=<slug>/<object_number>&color=none` (`make_map_url()`), which flies to the artwork and rings it, or says it isn't on the map yet (artworks loaded after the last `make art-map`).
- "See on map" on Visual Search results links to `/map/?q=<query>&color=none` (`make_map_search_url()`). Both links start with colours off so the artwork or matches stand out.

## Colours and legend filters

- Points are coloured by century (the default; by `production_date_start`, falling back to the end year; groups and slugs are `CENTURY_SLUGS` in `constants/museums.py`, the last one being "undated"), work type or museum.
- Clicking the active colour-mode button turns colours off (`color=none`): points go pale grey, with a faint second pass (`_buildDensityLayer()`, left out during a search) that darkens where they crowd together, and search matches (or, with no search, the selected artwork) get `HIGHLIGHT_COLOR`, since they would otherwise be the same grey. Searching from the map's own box keeps the current mode. There is no legend in this mode; filters still apply and the panel says how many are hidden.
- Clicking a legend item hides or shows that museum, work type or century; all three kinds of filter apply in every colour mode. "Show all" and "Hide all" act on the current colour mode only (Hide all, then click one item to isolate it).
- Filters run on the GPU via deck.gl's `DataFilterExtension` (a per-point 0/1 visibility value, `_visibilityMask()`), so hidden points are neither drawn nor picked.
- The chevron next to the colour-mode buttons collapses the legend items; it starts collapsed below 640px wide (phones), and while collapsed still says how many museums/work types/centuries are hidden.

## Performance

- The artworks layer gets positions, colours and the visibility mask as binary attributes (typed arrays kept outside Alpine's reactive state), not per-point accessors: accessors through Alpine's proxies took ~3 s to set up for ~180k points.
- The page preloads the geometry in `<head>` and parses the metadata only after the first frame.

## Search box

- Top right (above the legend on phones). Runs a Visual Search via `/map/search/?query=...` (`art_map_search_view`): JSON `[museum_slug, object_number]` pairs of the top `MAP_SEARCH_RESULTS` (200), unfiltered, so one Jina call per query. Shares the website search's per-IP rate limit budget (30/min, 200/hour) via `SEARCH_RATE_GROUP`.
- Draws the matches on top, dims the rest and zooms to where they gather (ignoring the 5% furthest out on each side). Legend filters hide matches too; "See as list" opens the same query on the home page.
- `museum:object_number` queries work as on the home page (similar artworks, no Jina call).

## URL state

The map keeps the search (`q`), selection, view (`x`, `y`, `z`), colour mode (`color=work_type`, `color=museum`, `color=none`) and filters (`hide_museums=smk,rma`, `hide_types=print`, `hide_centuries=1500s,undated`) in the URL, so map links can be shared.

## Geometry blob

`count, x, y, museum, work type, century`. The page reads blobs made before the century array was added and hides the Century mode (falling back to Work type) until `make art-map` is re-run.
