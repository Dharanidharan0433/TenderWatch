"""
detectors/vendor_concentration.py
------------------------------------
Detector: Vendor Concentration

Flags tenders where the awarded vendor holds a disproportionately high
share of awards within the SAME region + category peer group, relative
to how many distinct vendors normally compete in that group. A vendor
winning far more than an even share of a region/category's tenders is
a pattern worth investigating -- it does not, by itself, indicate
wrongdoing (regions with very few qualified specialist vendors will
naturally show some concentration), which is why the explanation
always states the comparison basis rather than asserting a conclusion.

Input contract:
    tenders_df must contain at least:
        tender_id, region, category, awarded_vendor_id

Output:
    list[DetectorResult], one per row in tenders_df.
"""

import pandas as pd

from detectors.base_detector import DetectorResult, not_triggered

DETECTOR_NAME = "Vendor Concentration"

# A vendor's win share within its region+category peer group above
# this threshold is flagged. 15% is chosen because with ~50 vendors
# competing for tenders spread across 6 regions x 10 categories, an
# even distribution would put any one vendor's expected share well
# under 10% -- 15%+ is a meaningful, explainable departure from that.
WIN_SHARE_THRESHOLD = 0.15

# Severity escalates further above the threshold, since "barely over"
# and "dominating the group" warrant different investigative urgency.
SEVERITY_HIGH_THRESHOLD = 0.30
SEVERITY_MEDIUM_THRESHOLD = 0.20

# A peer group with too few total tenders makes win-share statistically
# noisy (winning 2 of 3 tenders is 67% but isn't meaningful evidence of
# anything). Require a minimum group size before flagging at all.
MIN_GROUP_SIZE = 5

# Win share alone is not sufficient at small sample sizes: winning 2-3
# tenders out of ~15-20 in a peer group can clear a 15% share purely by
# chance. Requiring a minimum absolute win count alongside the share
# threshold filters out this small-sample noise while still catching
# genuine concentration (which tends to show up as both a high share
# AND a high absolute count).
MIN_VENDOR_WINS = 5


def _severity_for_share(win_share: float) -> str:
    """Maps a vendor's win share within its peer group to a severity label."""
    if win_share >= SEVERITY_HIGH_THRESHOLD:
        return "High"
    if win_share >= SEVERITY_MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def detect(tenders_df: pd.DataFrame) -> list[DetectorResult]:
    """
    Evaluates every tender in tenders_df for Vendor Concentration risk.

    Method:
        1. Group all awarded tenders by (region, category) to form
           peer groups -- tenders that genuinely compete in the same
           market segment.
        2. Within each peer group, compute each vendor's win count and
           win share (wins / total tenders in that group).
        3. Any tender whose awarded vendor's win share in that peer
           group exceeds WIN_SHARE_THRESHOLD is flagged, provided the
           peer group itself is large enough to be statistically
           meaningful (>= MIN_GROUP_SIZE tenders).

    Args:
        tenders_df: DataFrame with at least tender_id, region,
            category, awarded_vendor_id columns.

    Returns:
        One DetectorResult per row in tenders_df (preserving order is
        not guaranteed; callers should key results by tender_id).
    """
    required_cols = {"tender_id", "region", "category", "awarded_vendor_id"}
    missing = required_cols - set(tenders_df.columns)
    if missing:
        raise ValueError(f"tenders_df is missing required columns: {missing}")

    results: list[DetectorResult] = []

    # Drop rows with no awarded vendor (e.g. still-open tenders) --
    # concentration is only meaningful for completed awards.
    awarded_df = tenders_df.dropna(subset=["awarded_vendor_id"]).copy()

    # Peer group size: total awarded tenders sharing the same region+category.
    group_sizes = (
        awarded_df.groupby(["region", "category"])["tender_id"]
        .count()
        .rename("group_size")
    )

    # Win counts per (region, category, vendor) -- how many of that
    # peer group's tenders each vendor specifically won.
    vendor_wins = (
        awarded_df.groupby(["region", "category", "awarded_vendor_id"])["tender_id"]
        .count()
        .rename("vendor_wins")
    )

    # Join group_size back onto vendor_wins to compute win_share per vendor per group.
    vendor_wins_df = vendor_wins.reset_index().merge(
        group_sizes.reset_index(), on=["region", "category"], how="left"
    )
    vendor_wins_df["win_share"] = vendor_wins_df["vendor_wins"] / vendor_wins_df["group_size"]

    # Index for fast per-row lookup: (region, category, vendor_id) -> (win_share, vendor_wins, group_size)
    lookup = vendor_wins_df.set_index(["region", "category", "awarded_vendor_id"])

    for _, row in tenders_df.iterrows():
        tender_id = row["tender_id"]
        region = row["region"]
        category = row["category"]
        vendor_id = row["awarded_vendor_id"]

        if pd.isna(vendor_id):
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                "No awarded vendor on record; vendor concentration is not applicable.",
            ))
            continue

        key = (region, category, vendor_id)
        if key not in lookup.index:
            # Should not normally happen since we built the lookup from
            # the same awarded_df, but guard defensively.
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                "Insufficient peer group data to assess vendor concentration.",
            ))
            continue

        record = lookup.loc[key]
        group_size = int(record["group_size"])
        vendor_wins_count = int(record["vendor_wins"])
        win_share = float(record["win_share"])
        win_share_pct = round(win_share * 100, 1)
        threshold_pct = round(WIN_SHARE_THRESHOLD * 100, 1)

        if group_size < MIN_GROUP_SIZE:
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                f"Only {group_size} tender(s) recorded for {region} / {category}; "
                f"too few to assess vendor concentration reliably.",
                supporting_metric=f"group_size={group_size}",
            ))
            continue

        if win_share > WIN_SHARE_THRESHOLD and vendor_wins_count >= MIN_VENDOR_WINS:
            severity = _severity_for_share(win_share)
            results.append(DetectorResult(
                tender_id=tender_id,
                detector_name=DETECTOR_NAME,
                triggered=True,
                severity=severity,
                explanation=(
                    f"Awarded vendor won {vendor_wins_count} of {group_size} tenders "
                    f"({win_share_pct}%) in {region} / {category}, exceeding both the "
                    f"{threshold_pct}% concentration threshold and the minimum "
                    f"{MIN_VENDOR_WINS}-award pattern size for this peer group."
                ),
                supporting_metric=(
                    f"win_share={win_share_pct}%;threshold={threshold_pct}%;"
                    f"vendor_wins={vendor_wins_count};group_size={group_size}"
                ),
            ))
        else:
            results.append(not_triggered(
                tender_id, DETECTOR_NAME,
                f"Awarded vendor won {vendor_wins_count} of {group_size} tenders "
                f"({win_share_pct}%) in {region} / {category}, within the normal range.",
                supporting_metric=(
                    f"win_share={win_share_pct}%;threshold={threshold_pct}%"
                ),
            ))

    return results
