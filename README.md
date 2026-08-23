# Hartford school enrollment — hartfordschoolenrollment.us

A static dashboard tracking Hartford Public Schools enrollment, 1986-87 through 2024-25,
plus the reproducible pipeline that builds its data.

## Rebuilding the data

```
pip install pandas
python build_hartford_panel.py
```

That one command reads the raw source files, applies the filters, writes four CSVs to
`data/`, and rewrites the embedded data block inside `index.html`. Refresh the browser
and the dashboard reflects the change. There is no build step and no spreadsheet in the loop.

To change what qualifies as a long-running school, edit the two constants at the top of
the script and rerun:

| Constant | Current | Meaning |
| --- | --- | --- |
| `MIN_CONSECUTIVE_YEARS` | 30 | longest unbroken run of reported years |
| `MIN_ENROLLMENT_FLOOR` | 150 | no single year may fall below this |

At these settings, 24 of 70 Hartford schools qualify.

## Where the numbers come from

**1986-87 to 1997-98** — NCES Common Core of Data, Public School Universe Survey.
Fixed-width annual files in `data_full/psu8697_dat/`, downloaded from
<https://nces.ed.gov/ccd/data/zip/psu86ai_dat.zip> (swap `86` for `87`…`97`).
Each file is national, split alphabetically by state; Connecticut falls in the "ai" group.

**1998 to 2024** — Urban Institute Education Data Portal export,
`data_full/EducationDataPortal_08.22.2026_all_files/`. Pulled from
<https://educationdata.urban.org/>.

The two are joined on the 12-digit NCES school ID, never on school name — Hartford renamed
many of these schools over the period.

The total-enrollment field moves position between years as NCES widened its grade columns
(character 243 in 1986-87, 258 by 1988, 263 from 1991). Those offsets are recorded in the
`MEMBER_FIELD` map in the script and were verified against NCES ELSI: all 17 continuously
reporting Hartford schools matched exactly across all twelve years.

## Filters and adjustments

1. **Interpolation.** Blank years *inside* a school's lifespan are filled with the mean of
   up to two reported years on each side. Nothing is invented before a school opened or
   after it closed. Every filled value is flagged `is_interpolated`, and the script prints
   each one on every run — 14 values across 6 schools at present.
2. **Run length.** A school must have `MIN_CONSECUTIVE_YEARS` unbroken years of data.
3. **Size floor.** No year may fall below `MIN_ENROLLMENT_FLOOR`. This exists to exclude
   tiny specialty programs, not to exclude schools that shrank — the shrinking is the
   subject of the analysis. Keep the floor low for that reason.

## Files

| Path | What it is |
| --- | --- |
| `index.html` | the dashboard; data embedded, Chart.js from CDN |
| `build_hartford_panel.py` | the whole pipeline |
| `data/hartford_final_table.csv` | the filtered cohort, tidy — for spreadsheets |
| `data/hartford_enrollment_long.csv` | all 70 schools, all years, with filter verdict |
| `data/hartford_school_summary.csv` | per-school features and why each passed or failed |
| `data/hartford_school_enrollment_by_school_by_year.csv` | cohort pivoted wide; linked from the page |
| `data/ccd_vs_edsight_comparison.csv` | older CCD-vs-state cross-check; predates this pipeline |
| `data_full/` | raw sources; not needed to serve the site |
| `CNAME` | custom domain for GitHub Pages |

Data is embedded in `index.html` rather than fetched, so opening the file straight off disk
works — browsers block `fetch()` against local files.

## Deploying

Upload `index.html`, `CNAME`, and `data/` to a public GitHub repo. Settings → Pages →
deploy from `main` / root, custom domain `hartfordschoolenrollment.us`. Point the domain's
DNS at GitHub with four A records for `@`:

```
185.199.108.153
185.199.109.153
185.199.110.153
185.199.111.153
```

For `www`, add a CNAME record pointing at `<username>.github.io`. Enable "Enforce HTTPS"
once the DNS check passes. `data_full/` does not need to be uploaded.

## Known gaps

The enrollment trend chart is fully sourced and reproducible. The school-choice breakdown
chart is not: its pre-2016 magnet, charter, and Open Choice splits are modelled estimates,
as are the interpolated population figures behind the enrollment-rate assumption. Only the
2016-2025 portion of that chart comes from CT EdSight resident-town data. Anyone relying on
that second chart should be told which parts are estimated.
