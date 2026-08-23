# Raw source data

Everything `build_hartford_panel.py` reads. Committed deliberately so the analysis is
reproducible end to end — clone the repo, run the script, get the same numbers.

None of this is needed to serve the site. `index.html` carries its data embedded.

## `psu8697_dat/` — NCES Common Core of Data, 1986-87 to 1997-98

Public School Universe Survey, fixed-width text, one file per school year.
Downloaded from `https://nces.ed.gov/ccd/data/zip/psu86ai_dat.zip`, swapping `86` for
`87` … `97`, then unzipped.

Each file is **national**, not Connecticut-only. NCES splits each year across three files
by state alphabetically; `ai` covers Alabama through Iowa, which is where Connecticut falls.
The other two groups (`kn`, `ow`) aren't needed here.

Filenames are inconsistent across years — `psu86ai.txt`, `SCH94AI.DAT`, `SCHL95AI.DAT`,
`sch96ai.dat` — because NCES changed its conventions. The script matches them with a
regex rather than a fixed list.

Record layouts: `https://nces.ed.gov/ccd/data/txt/psu86lay.txt` (same year swap). Read them
before changing the parser. The total-enrollment field moves position across years, and
reading the wrong offset silently returns a single grade's count instead of the total.

## `EducationDataPortal_08.22.2026_all_files/` — Urban Institute, 1998 to 2024

CSV export from <https://educationdata.urban.org/>, K-12 → Schools → Connecticut →
Hartford School District, all years, student enrollment. Includes schools that have since
closed, which is why it's used instead of the NCES ELSI table generator — ELSI builds its
row list from the most recent year and silently omits closed schools.

`EducationDataPortal_08.22.2026_datadictionary.csv` documents the columns.

## Licensing

Both sources are U.S. federal government works in the public domain. The Urban Institute
Education Data Portal is released under a permissive license; see
<https://educationdata.urban.org/documentation/> for their preferred citation.
