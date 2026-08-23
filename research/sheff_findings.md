# Sheff record — data point tracker

Companion to `sheff_data_tracker.csv`. 32 points, 2002-03 through 2024-25.

## The single most useful finding

The Sheff compliance metric and the EdSight measure land in nearly the same place where
they overlap:

| Year | Measure | Value |
| --- | --- | --- |
| 2015-16 | Hartford minority students in reduced isolation (Sheff) | 45.5% |
| 2016-17 | Magnets & choice as share of all Hartford residents (EdSight) | 49.6% |

Those are different populations — Sheff counts minority students only, and excludes magnets
that failed its desegregation standard. But a ~4-point gap in adjacent years suggests the
Sheff percentage works as a **conservative proxy** for the magnets-and-choice share, running
slightly below it. That is the bridge for reconstructing the middle years.

Applying it:

| Year | Sheff rate | Implied magnets & choice share |
| --- | --- | --- |
| 2002-03 | 10% (or 17% — unresolved) | ~10-20% |
| 2006-07 | 11% | ~12-15% |
| 2012-13 | 37% | ~40% |
| 2014-15 | 44.5% | ~48% |
| 2016-17 | — | 49.6% (measured) |

That is a defensible trajectory: roughly 10-15% in the early 2000s rising to about half by
the mid-2010s. It is anchored at both ends and at three points between.

## What each source actually gives you

**Open Choice is the clean one.** Hartford-resident counts for 2003-04 through 2006-07 (809,
1,020, 1,062, 1,070) are directly comparable to EdSight's 2,076 in 2016-17. Same programme,
same basis, same unit. Roughly a doubling over a decade.

**The "new magnet" figures are a trap.** 532 / 635 / 1,734 / 2,006 count only seats in magnets
opened under the 2003 stipulation — not total Hartford magnet enrolment. Reading them as
magnet totals would badly understate the early 2000s. Flagged in the tracker.

**Vo-tech has a better route.** Don't use the Sheff record for CTECS. All 16 CTECS schools
report continuously in NCES CCD from 1986-87, and that is already in the ELSI export in
`data_full/`. It measures attendance rather than residence, but for the three Hartford-area
technical high schools that is a close approximation.

## Problems to resolve before publishing

1. **2002-03 baseline: 10% or 17%?** Both circulate in the litigation record. They may be
   different measures — one all Hartford minority students, one only those in the specific
   remedy programmes. Needs the primary stipulation.
2. **2007: 9% or 11%?** Same issue, adjacent sources disagree.
3. **47.5% is a target, not a result.** It appears in the Phase IV stipulation as a goal and
   is widely misquoted as an achieved figure for 2014-15. The actual is 44.5%, derived from
   the 9,558-of-21,458 count.
4. **A definitional break in 2013.** Phase III redefined "minority" from all non-white to
   Black and Hispanic only. That change alone moved eight magnets into compliance with zero
   change in enrolment. Any rate series crossing 2013 is not internally consistent, and the
   break should be drawn on the chart, not smoothed over.
5. **2015-16's 9,108 runs backwards.** It sits below 2014-15's 9,558, which contradicts the
   rising trend. Probably a different basis. Marked low confidence.

## Leads not yet exhausted

- **Cotto & Feder, Choice Watch (CT Voices for Children, 2014)** — the most promising single
  document; profiles Hartford magnet, charter and technical enrolment by year. The Trinity
  and ctvoices copies both returned empty on fetch. Retry, or request from CT Voices.
- **Orfield & Ee, Connecticut School Integration (UCLA Civil Rights Project, 2015)** — cited
  as the source for the year-by-year reduced-isolation series. Same fetch problem.
- **Phase II (2008) and Phase III (2013) stipulations** — Phase IV was retrieved and is
  almost entirely legal terms and funding, no enrolment tables. The earlier two may differ.
  Phase IV does confirm at line 261 that SDE produces "Hartford annual reports disaggregating
  Hartford resident students," which is the document to ask for by name.
- **Robert Cotto** — co-author of Choice Watch, formerly of Trinity, has published a CV of
  related work. A second contact alongside Dougherty.

## Honest read

There is enough here to build a defensible proxy back to roughly 2002, with five real anchor
points and a calibration check against the measured EdSight years. There is nothing here for
1986-2001, and I found no indication such figures were ever compiled — the remedy programmes
barely existed before the 1996 ruling, so the category is close to empty by construction
rather than merely unmeasured. That is worth stating on the page as a finding in itself.
