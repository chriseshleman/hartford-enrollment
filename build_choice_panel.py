"""
Build the Hartford-resident enrolment-by-school-type panel, 2002-03 to 2024-25.

This is the second of two pipelines. `build_hartford_panel.py` produces the
school-level enrolment series (chart one) entirely from measured data. This one
produces the by-school-type series (chart two), which is measured from 2016-17
and reconstructed before that.

Three categories, three methods, all anchored in federal data:

  Traditional        2016-24 measured (EdSight). Earlier years taken from
                     enrolment in NON-MAGNET Hartford district schools, per CCD.
                     Neighbourhood schools serve essentially only residents, and
                     the two measures agree to within 1-5% across six overlapping
                     years -- so this is close to a direct read, not an estimate.
  Vo-tech            2016-24 measured (EdSight). Earlier years scaled from
                     A. I. Prince Technical High School's enrolment, which CCD
                     reports continuously back to 1986-87.
  Magnets & choice   2016-24 measured (EdSight). Earlier years derived from the
                     Sheff v. O'Neill compliance rate -- the share of Hartford
                     minority students in reduced-isolation settings, which the
                     state reported under court order.

The resident total is then DERIVED rather than assumed. Given traditional (T),
vo-tech (V) and the magnets-and-choice share (s):

    R = (T + V) / (1 - s)          and     magnets & choice = R - T - V

An earlier version held the total flat at its first measured value. That is no
longer needed: two of the three categories now come from CCD directly, so the
total follows from them.

Why the Sheff rate is usable as a proxy: it reads 45.5% for 2015-16, against a
measured magnets-and-choice share of 49.6% for 2016-17. Different populations --
Sheff counts minority students only, and excludes magnets that failed its
desegregation standard -- but a ~4 point gap in adjacent years means it tracks
the same movement, slightly low. It is a conservative proxy, not a substitute.

Usage:
    python build_choice_panel.py

Writes a CSV to data/ and rewrites the `const CHOICE_RAW = {...};` block in
index.html. It does not touch the `const RAW = {...};` block, which belongs to
the other pipeline.
"""

from pathlib import Path
from datetime import date
import json
import re
import pandas as pd

# ---------------------------------------------------------------- config ----

ELSI_CSV   = Path("data_full/ELSI_CT_all_schools_1986_2024.csv")
EDP_CSV    = Path("data_full/EducationDataPortal_08.22.2026_all_files/"
                  "EducationDataPortal_08.22.2026_Schools.csv")
OUT_DIR    = Path("data")
INDEX_HTML = Path("index.html")

HARTFORD_LEAID = "0901920"

FIRST_YEAR, LAST_YEAR = 1986, 2024

# Before the 1996 Sheff ruling the choice programmes barely existed: charters
# opened in 1997, Open Choice in 1998. CCD bears this out rather than assuming
# it -- Hartford magnet enrolment reads 0 for 1999, 2000 and 2001, and just 116
# in 1998. So for these years traditional enrolment carries almost everything,
# and no interpolation is needed at all.
PRE_SHEFF_END = 2001

# --- Measured: CT SDE EdSight, Resident Town export, 2016-17 to 2024-25 ------
# Every Hartford-resident student, by the type of school attended.
EDSIGHT = {
    #  year: (traditional, sheff magnet, open choice, charter, vo-tech, other)
    2016: (11096, 7439, 2076, 1530, 630, 488),
    2017: (10978, 7317, 2075, 1617, 661, 481),
    2018: (10032, 7569, 2103, 1612, 606, 574),
    2019: ( 9370, 7828, 2112, 1666, 618, 692),
    2020: ( 8457, 8295, 2114, 1688, 631, 532),
    2021: ( 8363, 8001, 2063, 1579, 612, 648),
    2022: ( 8231, 8291, 2058, 1445, 594, 651),
    2023: ( 7951, 8785, 2061, 1363, 575, 571),
    2024: ( 7579, 8996, 2081, 1318, 610, 607),
}

# --- The Sheff compliance rate, 2002-03 to 2015-16 --------------------------
# Share of Hartford-resident Black and Latino students in reduced-isolation
# settings. 2004-05 onward is read from a compiled annual series (see
# OTL_CSV below), so no interpolation is needed across that stretch.
#
# Only 2002-03 is still a hand-picked anchor, taken from the plaintiffs' ten-
# year retrospective; 2003-04 is interpolated between it and the first reported
# year. An earlier version interpolated the whole 2002-2015 span from six
# scattered anchors. Checked against the compiled series, that came within a
# mean of 2.9 points -- but three of the six anchors were wrong by up to five,
# and the real series is not monotonic the way straight lines assume.
SHEFF_RATE_MANUAL = {
    2002: 10.0,   # plaintiffs' ten-year retrospective; record also shows 17%
}

# Compiled by Michael Kulik '23 and Maria Vicuna '24, Trinity College, from
# CSDE Sheff compliance reports (2019-2021) and a CT Mirror chart by Jacqueline
# Rabe Thomas (2004-2018). Published MIT-licensed at
# https://github.com/OnTheLine/otl-sheff-data
OTL_CSV = Path("research/otl_2004_2021_hartford_black_latino_diverse_schools.csv")
OTL_RATE_ROW = "Percent in Diverse"
OTL_USE_THROUGH = 2015   # past this, EdSight measures it directly

# In 2013 the Phase III stipulation redefined "minority" from all non-white to
# Black and Hispanic only. Eight magnets became compliant with no change in
# enrolment, so the rate series is not internally consistent across this year.
DEFINITION_BREAK_YEAR = 2013

# --- Traditional ------------------------------------------------------------
# Enrolment in non-magnet Hartford district schools, per CCD. Interdistrict
# magnets draw suburban students; neighbourhood schools essentially do not, so
# their enrolment is very close to a count of resident students in traditional
# schools. Across the six years where both measures exist the ratio of the
# EdSight resident count to the CCD non-magnet count stays between 0.99 and
# 1.05, so a single calibration factor is applied.
#
# Note: a whole-district denominator was tried first and rejected. The ratio of
# resident to district enrolment drifts from 1.17 to 1.35 across the measured
# years, because district enrolment is falling faster than resident enrolment --
# which is the very thing being measured. Splitting the district into magnet and
# non-magnet schools avoids that problem entirely.

# --- Vo-tech ----------------------------------------------------------------
# A. I. Prince Technical High School, in Hartford, reports continuously in CCD
# from 1986-87. Scaling its enrolment to the measured resident vo-tech counts
# absorbs both directions of error at once: Prince students who don't live in
# Hartford, and Hartford residents attending other CTECS schools.
PRINCE_NAME_MATCH = "PRINCE"


# ------------------------------------------------------------------ read ----

def read_prince_enrolment(path: Path) -> dict:
    """A. I. Prince Technical High School enrolment by year, from ELSI."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header = next(i for i, l in enumerate(lines) if l.startswith("School Name,"))
    df = pd.read_csv(path, skiprows=header, encoding="utf-8-sig", dtype=str)

    year_cols = {c: int(re.search(r"(\d{4})-\d{2}$", c).group(1))
                 for c in df.columns if c.startswith("Total Students")}
    row = df[df["School Name"].str.contains(PRINCE_NAME_MATCH, case=False, na=False)].iloc[0]
    return {y: int(float(row[c])) for c, y in year_cols.items() if pd.notna(row[c])}


def read_non_magnet_enrolment(path: Path) -> tuple:
    """Hartford district enrolment split by CCD's magnet flag, 1998 onward.

    Returns (non_magnet_by_year, magnet_by_year).
    """
    df = pd.read_csv(path, dtype=str)
    df = df[df["ncessch"].str.startswith(HARTFORD_LEAID, na=False)]
    df["year"] = df["year"].astype(int)
    df["enrollment"] = pd.to_numeric(df["enrollment"], errors="coerce")

    def total(flag):
        return (df[df["magnet"] == flag].groupby("year")["enrollment"]
                  .sum().round().astype(int).to_dict())

    return total("No"), total("Yes")


def read_sheff_rates(path: Path) -> dict:
    """Reported reduced-isolation rate by starting year, from the OTL series."""
    df = pd.read_csv(path, index_col=0)
    df.columns = [c.strip() for c in df.columns]
    df.index = [str(i).strip() for i in df.index]
    rates = {}
    for school_year in df.columns:
        year = int(school_year[:4])
        if year <= OTL_USE_THROUGH:
            rates[year] = round(float(df.loc[OTL_RATE_ROW, school_year]) * 100, 1)
    return rates


def read_district_totals() -> dict:
    """Total Hartford district enrolment 1986-1997, from the raw CCD files.

    Reuses the fixed-width parser from the school-level pipeline rather than
    duplicating it. Those files carry no magnet flag, but none is needed: the
    magnet programmes did not yet exist.
    """
    from build_hartford_panel import read_nces_fixed_width, NCES_DIR
    df = read_nces_fixed_width(NCES_DIR)
    return (df.dropna(subset=["enrollment"])
              .groupby("year_start")["enrollment"].sum().astype(int).to_dict())


# ------------------------------------------------------------ build panel ----

def interpolate(anchors: dict, first: int, last: int) -> dict:
    """Straight lines between anchor years; flat outside the anchored range."""
    years = sorted(anchors)
    out = {}
    for y in range(first, last + 1):
        if y in anchors:
            out[y] = anchors[y]
            continue
        below = [a for a in years if a < y]
        above = [a for a in years if a > y]
        if not below:
            out[y] = anchors[years[0]]
        elif not above:
            out[y] = anchors[years[-1]]
        else:
            lo, hi = below[-1], above[0]
            f = (y - lo) / (hi - lo)
            out[y] = anchors[lo] + (anchors[hi] - anchors[lo]) * f
    return out


def build(prince: dict, non_magnet: dict, magnet: dict, district: dict,
          reported_rates: dict) -> pd.DataFrame:
    votech_ratio = sum(EDSIGHT[y][4] / prince[y] for y in EDSIGHT) / len(EDSIGHT)

    overlap = [y for y in EDSIGHT if y in non_magnet]
    trad_ratio = sum(EDSIGHT[y][0] / non_magnet[y] for y in overlap) / len(overlap)

    # Reported figures win; the single manual anchor only fills the years before
    # the reported series starts.
    anchors = {**SHEFF_RATE_MANUAL, **reported_rates}
    rate = interpolate(anchors, min(anchors), max(anchors))
    self_reported = set(reported_rates)

    rows = []
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        votech = round(prince[year] * votech_ratio)

        if year in EDSIGHT:
            trad, mag, choice, charter, votech, other = EDSIGHT[year]
            mc = mag + choice + charter + other
            total = trad + mc + votech
            basis = "measured"

        elif year <= PRE_SHEFF_END:
            # Choice programmes barely existed. Traditional carries the years;
            # whatever magnet enrolment CCD records is added where it exists.
            base = non_magnet.get(year, district.get(year))
            trad = round(base * trad_ratio)
            mc = magnet.get(year, 0)
            total = trad + mc + votech
            basis = "pre-Sheff"

        else:
            trad = round(non_magnet[year] * trad_ratio)
            # Derive the resident total from the two known categories and the
            # Sheff share, rather than assuming it.
            total = round((trad + votech) / (1 - rate[year] / 100))
            mc = total - trad - votech
            basis = "reconstructed" if year in self_reported else "interpolated"

        rows.append({
            "school_year": f"{year}-{str((year + 1) % 100).zfill(2)}",
            "year_start": year,
            "traditional": trad,
            "magnets_and_choice": mc,
            "vo_tech": votech,
            "total": total,
            "magnets_and_choice_pct": round(100 * mc / total, 1),
            "basis": basis,
        })

    print(f"traditional scaling factor: {trad_ratio:.4f} "
          f"(CCD non-magnet district enrolment -> EdSight resident traditional, "
          f"{len(overlap)} overlapping years)")
    print(f"vo-tech scaling factor:     {votech_ratio:.4f} "
          f"(A. I. Prince enrolment -> Hartford-resident vo-tech)")
    return pd.DataFrame(rows)


# ------------------------------------------------------- inject into page ----

def inject(df: pd.DataFrame, index_html: Path = INDEX_HTML) -> bool:
    if not index_html.exists():
        print(f"  (skipped: {index_html} not found)")
        return False

    payload = {
        "years": df["school_year"].tolist(),
        "series": {
            "Traditional public schools": df["traditional"].tolist(),
            "Vo-tech schools": df["vo_tech"].tolist(),
            "Magnets & choice programs": df["magnets_and_choice"].tolist(),
        },
        "basis": df["basis"].tolist(),
        "definitionBreak": f"{DEFINITION_BREAK_YEAR}-"
                           f"{str((DEFINITION_BREAK_YEAR + 1) % 100).zfill(2)}",
        "firstMeasured": f"{min(EDSIGHT)}-{str((min(EDSIGHT) + 1) % 100).zfill(2)}",
    }

    html = index_html.read_text(encoding="utf-8")
    html = re.sub(r'(<span id="buildDate">)[^<]*(</span>)',
                  r"\g<1>" + date.today().strftime("%d %B %Y") + r"\g<2>", html)
    new, n = re.subn(r"const CHOICE_RAW = \{.*?\};",
                     "const CHOICE_RAW = " + json.dumps(payload) + ";",
                     html, count=1, flags=re.S)
    if not n:
        print("  (warning: no `const CHOICE_RAW = {...};` block found)")
        return False
    index_html.write_text(new, encoding="utf-8")
    return True


# ------------------------------------------------------------------- main ----

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    non_magnet, magnet = read_non_magnet_enrolment(EDP_CSV)
    rates = read_sheff_rates(OTL_CSV)
    print(f"reported Sheff rates: {min(rates)}-{max(rates)} "
          f"({len(rates)} years, no interpolation needed)")
    df = build(read_prince_enrolment(ELSI_CSV), non_magnet, magnet,
               read_district_totals(), rates)
    df.to_csv(OUT_DIR / "hartford_choice_panel.csv", index=False)

    counts = df["basis"].value_counts()
    print("years: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    print(f"\n{'year':<9}{'trad':>7}{'vo-tech':>9}{'mag+choice':>12}{'total':>8}"
          f"{'m+c %':>8}  basis")
    for r in df.itertuples():
        print(f"{r.school_year:<9}{r.traditional:>7,}{r.vo_tech:>9,}"
              f"{r.magnets_and_choice:>12,}{r.total:>8,}"
              f"{r.magnets_and_choice_pct:>7.1f}%  {r.basis}")

    if inject(df):
        print(f"\ninjected {len(df)} years into {INDEX_HTML}")
    print(f"wrote {OUT_DIR / 'hartford_choice_panel.csv'}")


if __name__ == "__main__":
    main()
