"""
Build a Hartford Public Schools enrollment panel, 1986-87 through 2024-25.

Sources
-------
1. NCES CCD Public School Universe, fixed-width files, 1986-87 .. 1997-98.
   Download: https://nces.ed.gov/ccd/data/zip/psu86ai_dat.zip  (swap 86 -> 87 ... 97)
   Connecticut lives in the "ai" group (states Alabama .. Iowa).

2. Urban Institute Education Data Portal CSV export, 1998 .. 2024.
   https://educationdata.urban.org/  -> K-12 / Schools / Connecticut / Hartford

Both are unioned on the 12-digit NCES school ID (ncessch). Never join on school
name: Hartford renamed many schools over these 40 years.

Usage
-----
    python build_hartford_panel.py

Edit NCES_DIR and EDP_CSV below to point at your local copies.
Outputs three CSVs into OUT_DIR, ready to upload to Google Sheets.
"""

from pathlib import Path
import json
import re
import pandas as pd

# ---------------------------------------------------------------- config ----

NCES_DIR = Path("data_full/psu8697_dat")   # folder holding the 12 unzipped files
EDP_CSV  = Path("data_full/EducationDataPortal_08.22.2026_all_files/"
                "EducationDataPortal_08.22.2026_Schools.csv")
OUT_DIR  = Path("data")

HARTFORD_LEAID = "0901920"   # NCES district ID; ncessch starts with this
FIRST_YEAR, LAST_YEAR = 1986, 2024

MIN_CONSECUTIVE_YEARS = 30   # filter 1
MIN_ENROLLMENT_FLOOR  = 150  # filter 2: no year may fall below this

# The total-enrollment field ("MEMBER") moves position between years, because
# NCES widened the grade-level fields over time. Positions below are 1-indexed
# start + width, taken from the official record layouts
# (https://nces.ed.gov/ccd/data/txt/psu86lay.txt, ...psu97lay.txt) and verified
# against ELSI: all 17 continuously-reporting Hartford schools matched exactly
# in all 12 years.
MEMBER_FIELD = {
    1986: (243, 5), 1987: (243, 5),
    1988: (258, 6), 1989: (258, 6), 1990: (258, 6),
    1991: (263, 6), 1992: (263, 6), 1993: (263, 6), 1994: (263, 6),
    1995: (263, 6), 1996: (263, 6), 1997: (263, 6),
}

NCESSCH_SPAN  = (1, 12)    # constant across all years
SCHOOLNAME_SPAN = (77, 30) # constant across all years


# ------------------------------------------------------------- read NCES ----

def read_nces_fixed_width(directory: Path) -> pd.DataFrame:
    """Parse the 12 fixed-width CCD school universe files into a tidy frame."""
    rows = []
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in (".txt", ".dat"):
            continue
        # filenames are inconsistent: psu86ai.txt, SCH94AI.DAT, SCHL95AI.DAT ...
        match = re.search(r"(?:psu|schl|sch)(\d{2})ai", path.name, re.I)
        if not match:
            continue
        year = 1900 + int(match.group(1))
        start, width = MEMBER_FIELD[year]

        with open(path, encoding="latin-1", errors="replace") as fh:
            for line in fh:
                ncessch = line[NCESSCH_SPAN[0] - 1: NCESSCH_SPAN[0] - 1 + NCESSCH_SPAN[1]]
                if not ncessch.startswith(HARTFORD_LEAID):
                    continue
                name = line[SCHOOLNAME_SPAN[0] - 1:
                            SCHOOLNAME_SPAN[0] - 1 + SCHOOLNAME_SPAN[1]].strip()
                raw = line[start - 1: start - 1 + width].strip()
                rows.append({
                    "ncessch": ncessch,
                    "school_name": name,
                    "year_start": year,
                    "enrollment": int(raw) if raw.isdigit() else None,
                })
    return pd.DataFrame(rows)


# -------------------------------------------------------------- read EDP ----

def read_education_data_portal(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"ncessch": str})
    df = df[df["ncessch"].str.startswith(HARTFORD_LEAID, na=False)]
    df = df.rename(columns={"year": "year_start"})
    df["year_start"] = df["year_start"].astype(int)
    df["enrollment"] = pd.to_numeric(df["enrollment"], errors="coerce")
    return df[["ncessch", "school_name", "year_start", "enrollment"]]


# ---------------------------------------------------------------- shaping ---

def build_panel(nces: pd.DataFrame, edp: pd.DataFrame) -> pd.DataFrame:
    panel = pd.concat([nces, edp], ignore_index=True)
    panel = panel[panel["year_start"].between(FIRST_YEAR, LAST_YEAR)]
    panel = panel[panel["enrollment"].isna() | (panel["enrollment"] > 0)]

    # Canonical name = whatever the school was called most recently.
    canonical = (panel.dropna(subset=["school_name"])
                      .sort_values("year_start")
                      .groupby("ncessch")["school_name"].last()
                      .str.title().to_dict())

    # Expand to a complete school x year grid so gaps become explicit blanks
    # rather than silently-absent rows.
    grid = pd.MultiIndex.from_product(
        [sorted(panel["ncessch"].unique()), range(FIRST_YEAR, LAST_YEAR + 1)],
        names=["ncessch", "year_start"],
    ).to_frame(index=False)

    panel = grid.merge(
        panel.drop(columns=["school_name"]).drop_duplicates(["ncessch", "year_start"]),
        on=["ncessch", "year_start"], how="left",
    )
    panel["school_name"] = panel["ncessch"].map(canonical)
    return panel


NEIGHBOURS_EACH_SIDE = 2   # how many reported years to average from each side


def interpolate_interior_gaps(panel: pd.DataFrame) -> pd.DataFrame:
    """Fill missing years inside a school's lifespan by averaging its neighbours.

    For each blank year we take up to NEIGHBOURS_EACH_SIDE reported values before
    it and up to that many after it, and average whatever is available.

    Only *interior* gaps are filled -- years between a school's first and last
    reported year. Nothing is invented before a school opened or after it closed,
    which would otherwise manufacture enrollment for schools that no longer exist.

    Every filled value is flagged in `is_interpolated` so it can be excluded or
    styled differently downstream.
    """
    panel = panel.sort_values(["ncessch", "year_start"]).copy()
    panel["is_interpolated"] = False

    for _, group in panel.groupby("ncessch"):
        values = group["enrollment"].tolist()
        index = group.index.tolist()

        reported = [i for i, v in enumerate(values) if pd.notna(v)]
        if len(reported) < 2:
            continue
        first, last = reported[0], reported[-1]

        for i in range(first + 1, last):
            if pd.notna(values[i]):
                continue
            before = [values[j] for j in reported if j < i][-NEIGHBOURS_EACH_SIDE:]
            after  = [values[j] for j in reported if j > i][:NEIGHBOURS_EACH_SIDE]
            window = before + after
            if not window:
                continue
            panel.loc[index[i], "enrollment"] = round(sum(window) / len(window))
            panel.loc[index[i], "is_interpolated"] = True

    return panel


def longest_consecutive_run(values) -> int:
    best = current = 0
    for value in values:
        current = current + 1 if pd.notna(value) else 0
        best = max(best, current)
    return best


def summarise(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (ncessch, name), group in panel.groupby(["ncessch", "school_name"]):
        group = group.sort_values("year_start")
        reported = group["enrollment"].dropna()
        if reported.empty:
            continue
        years = group.loc[group["enrollment"].notna(), "year_start"]
        rows.append({
            "ncessch": ncessch,
            "school_name": name,
            "first_year": int(years.min()),
            "last_year": int(years.max()),
            "n_years_reported": len(reported),
            "n_years_interpolated": int(group["is_interpolated"].sum()),
            "longest_consecutive_run": longest_consecutive_run(group["enrollment"]),
            "min_enrollment": int(reported.min()),
            "max_enrollment": int(reported.max()),
            "years_below_floor": int((reported < MIN_ENROLLMENT_FLOOR).sum()),
        })

    summary = pd.DataFrame(rows)
    summary["passes_run"]   = summary["longest_consecutive_run"] >= MIN_CONSECUTIVE_YEARS
    summary["passes_floor"] = summary["years_below_floor"] == 0
    summary["INCLUDE"]      = summary["passes_run"] & summary["passes_floor"]
    return summary


# ------------------------------------------------------- dashboard export ---

INDEX_HTML = Path("index.html")


def inject_into_dashboard(panel: pd.DataFrame, summary: pd.DataFrame,
                          index_html: Path = INDEX_HTML) -> int:
    """Rewrite the `const RAW = {...}` block in index.html with current data.

    The dashboard embeds its data rather than fetching it, so that opening
    index.html straight off disk still works -- browsers block fetch() against
    local files. Embedding costs nothing once hosted.
    """
    if not index_html.exists():
        print(f"  (skipped: {index_html} not found)")
        return 0

    included = panel[panel["ncessch"].isin(summary.loc[summary["INCLUDE"], "ncessch"])]
    years = sorted(included["school_year"].unique(),
                   key=lambda s: int(s[:4]))

    schools = {}
    for name, group in included.groupby("school_name"):
        by_year = dict(zip(group["school_year"], group["enrollment"]))
        schools[name] = [None if pd.isna(by_year.get(y)) else float(by_year[y])
                         for y in years]

    payload = json.dumps({"years": years, "schools": schools})
    html = index_html.read_text(encoding="utf-8")
    new_html, count = re.subn(r"const RAW = \{.*?\};",
                              "const RAW = " + payload + ";",
                              html, count=1, flags=re.S)
    if count:
        index_html.write_text(new_html, encoding="utf-8")
    else:
        print("  (warning: no `const RAW = {...};` block found in index.html)")
    return len(schools)


# ------------------------------------------------------------------- main ---

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    panel = build_panel(read_nces_fixed_width(NCES_DIR),
                        read_education_data_portal(EDP_CSV))
    panel = interpolate_interior_gaps(panel)

    panel["school_year"] = (panel["year_start"].astype(str) + "-"
                            + ((panel["year_start"] + 1) % 100).map("{:02d}".format))
    panel = panel[["ncessch", "school_name", "school_year", "year_start",
                   "enrollment", "is_interpolated"]]
    panel = panel.sort_values(["school_name", "year_start"])

    summary = summarise(panel)

    keep = set(summary.loc[summary["INCLUDE"], "ncessch"])
    panel["include"] = panel["ncessch"].isin(keep)
    final = panel[panel["include"]].drop(columns=["include"])

    # every school, every year, with the filter verdict attached
    panel.to_csv(OUT_DIR / "hartford_enrollment_long.csv", index=False)

    # per-school features and why each school passed or failed
    (summary.sort_values(["INCLUDE", "school_name"], ascending=[False, True])
            .to_csv(OUT_DIR / "hartford_school_summary.csv", index=False))

    # the filtered cohort, tidy -- for spreadsheets and ad-hoc analysis
    final.to_csv(OUT_DIR / "hartford_final_table.csv", index=False)

    # the same cohort pivoted wide -- linked from the dashboard as "full data"
    (final.pivot_table(index="school_year", columns="school_name",
                       values="enrollment")
          .reindex(sorted(final["school_year"].unique(), key=lambda s: int(s[:4])))
          .to_csv(OUT_DIR / "hartford_school_enrollment_by_school_by_year.csv"))

    filled = panel[panel["is_interpolated"]]
    print(f"schools: {len(summary)}   included: {int(summary['INCLUDE'].sum())}")
    print(f"observations: {int(panel['enrollment'].notna().sum())} "
          f"({len(filled)} interpolated)")
    if not filled.empty:
        print("\ninterpolated years (interior gaps only):")
        for name, rows in filled.groupby("school_name"):
            years = ", ".join(f"{r.school_year}={int(r.enrollment)}"
                              for r in rows.itertuples())
            print(f"  {name:<45} {years}")
    print(f"\nwrote 4 files to {OUT_DIR.resolve()}")

    n = inject_into_dashboard(panel, summary)
    if n:
        print(f"injected {n} schools x {panel['school_year'].nunique()} years "
              f"into {INDEX_HTML}")


if __name__ == "__main__":
    main()
