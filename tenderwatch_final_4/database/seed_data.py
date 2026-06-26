"""
database/seed_data.py
------------------------
Synthetic data generator for TenderWatch.

Generates a realistic government procurement dataset:
    - 50 vendors across multiple regions and category specializations
    - 1000 tenders across multiple categories and regions
    - Bids for each tender (1 winning bid + competing bids)

Dataset composition:
    - 95% of tenders are "clean" -- generated from normal, realistic
      statistical distributions with no deliberate irregularities.
    - 5% of tenders (50 of 1000) are deliberately mutated to embed one
      of five anomaly patterns, split roughly evenly across:
        1. Vendor Concentration
        2. Bid Clustering
        3. Single Bidder
        4. Short Tender Window
        5. Price Inflation

IMPORTANT -- ground truth vs. detection:
    The `is_synthetic_anomaly` and `anomaly_type` columns are GROUND
    TRUTH markers written here for dataset validation purposes only
    (e.g. confirming detector precision/recall during development).
    They are not consulted by the detectors at runtime, and the
    platform never surfaces them to end users as a confirmed verdict.
    Each anomaly is injected by altering the actual underlying data
    (bid amounts, dates, vendor win distribution) so that a detector
    working ONLY from tenders/bids data would have a genuine signal
    to find -- this is what makes the detectors meaningfully testable.

This module is intentionally free of any database connection logic;
it only builds Python data structures. database/db.py handles all
actual writes, keeping "what data looks like" separate from
"how data gets persisted".
"""

import random
from datetime import date, timedelta

from database.db import initialize_database, execute_many, execute_write

# Fixed seed for reproducibility -- every team member who runs this
# script gets an identical dataset, which matters for demoing and for
# comparing detector behavior across development sessions.
random.seed(42)

# ----------------------------------------------------------------------
# REFERENCE DATA
# ----------------------------------------------------------------------

REGIONS = [
    "North Zone", "South Zone", "East Zone", "West Zone",
    "Central Zone", "North-East Zone",
]

CATEGORIES = [
    "Road Construction", "IT Infrastructure", "Medical Equipment",
    "School Supplies", "Sanitation Services", "Electrical Works",
    "Office Furniture", "Security Services", "Water Supply Projects",
    "Public Transport Maintenance",
]

DEPARTMENTS = [
    "Public Works Department", "Health Department", "Education Department",
    "Urban Development Authority", "Municipal Corporation",
    "Transport Department", "Rural Development Department",
]

VENDOR_NAME_PREFIXES = [
    "National", "United", "Apex", "Reliable", "Premier", "Sterling",
    "Capital", "Eastern", "Western", "Bharat", "Metro", "Allied",
    "Pioneer", "Continental", "Crown", "Summit", "Horizon", "Vertex",
]

VENDOR_NAME_SUFFIXES = [
    "Infrastructure Pvt. Ltd.", "Constructions Ltd.", "Enterprises",
    "Engineering Works", "Contractors Pvt. Ltd.", "Industries Ltd.",
    "Services Pvt. Ltd.", "Builders Ltd.", "Solutions Pvt. Ltd.",
    "Supplies Co.",
]

# Base date range from which all publish dates are drawn.
DATASET_START_DATE = date(2023, 1, 1)
DATASET_END_DATE = date(2025, 12, 31)
DATE_RANGE_DAYS = (DATASET_END_DATE - DATASET_START_DATE).days

# Tender counts and anomaly composition, kept as named constants so the
# 95/5 split and per-anomaly-type counts are easy to audit and adjust.
TOTAL_TENDERS = 1000
TOTAL_VENDORS = 50
ANOMALY_RATIO = 0.05
TOTAL_ANOMALOUS_TENDERS = int(TOTAL_TENDERS * ANOMALY_RATIO)  # 50

ANOMALY_TYPES = [
    "Vendor Concentration",
    "Bid Clustering",
    "Single Bidder",
    "Short Tender Window",
    "Price Inflation",
]


def _random_date(start: date, end: date) -> date:
    """Returns a random date between start and end (inclusive)."""
    span = (end - start).days
    return start + timedelta(days=random.randint(0, span))


# ----------------------------------------------------------------------
# VENDOR GENERATION
# ----------------------------------------------------------------------

def generate_vendors(count: int = TOTAL_VENDORS) -> list[dict]:
    """
    Generates `count` synthetic vendors with plausible names,
    registration numbers, regions, and category specializations.

    A small subset (the vendors later used in Vendor Concentration
    anomalies) are pre-marked `is_flagged_entity = True`. This flag
    is ground-truth metadata only -- it has no influence on the bid
    or award data generated for them; it exists purely so developers
    can later check "did the Vendor Concentration detector catch the
    vendors we intentionally concentrated awards on?"

    Returns:
        List of vendor dicts, each with keys matching the `vendors`
        table columns (excluding vendor_id, which SQLite assigns).
    """
    vendors = []
    used_names = set()

    for i in range(count):
        # Ensure unique vendor names by retrying on collision -- with
        # 18 prefixes x 10 suffixes there's enough combinatorial space
        # for 50 unique vendors without exhausting it.
        while True:
            name = f"{random.choice(VENDOR_NAME_PREFIXES)} {random.choice(VENDOR_NAME_SUFFIXES)}"
            if name not in used_names:
                used_names.add(name)
                break

        registration_number = f"REG-{2020 + (i % 5)}-{10000 + i}"
        region = random.choice(REGIONS)
        category_specialization = random.choice(CATEGORIES)
        date_registered = _random_date(date(2015, 1, 1), date(2022, 12, 31))

        vendors.append({
            "vendor_name": name,
            "registration_number": registration_number,
            "region": region,
            "category_specialization": category_specialization,
            "date_registered": date_registered.isoformat(),
            # First 6 vendors are reserved as "concentration anomaly"
            # vendors -- see inject_vendor_concentration_anomalies().
            "is_flagged_entity": i < 6,
        })

    return vendors


# ----------------------------------------------------------------------
# CLEAN TENDER + BID GENERATION (the 95% baseline)
# ----------------------------------------------------------------------

def generate_clean_tenders(vendor_ids: list[int], count: int, start_index: int = 0) -> list[dict]:
    """
    Generates `count` realistic, non-anomalous tenders.

    Each tender gets:
        - A realistic tender window (10-45 days between publish and
          deadline -- short enough to feel real, long enough to not
          look suspicious).
        - An estimated value drawn from a category-plausible range.
        - An awarded value close to (but not exactly) the estimate,
          simulating normal negotiation variance (+/- 8%).
        - A winning vendor chosen close to uniformly at random, so no
          single vendor dominates a category/region (this absence of
          concentration is what makes the clean data clean).

    Args:
        vendor_ids: Pool of vendor_id values to award tenders to.
        count: Number of clean tenders to generate.
        start_index: Offset used to build `tender_reference` numbers.
            This function may be called multiple times (once for the
            clean batch, once for the to-be-mutated anomaly batch) --
            callers MUST pass non-overlapping ranges so every
            tender_reference stays globally unique across both calls.

    Returns:
        List of tender dicts (without tender_id, which SQLite assigns).
    """
    tenders = []

    for offset in range(count):
        i = start_index + offset
        category = random.choice(CATEGORIES)
        region = random.choice(REGIONS)
        department = random.choice(DEPARTMENTS)

        # Estimated value: wide realistic range across categories
        # (lakhs to a few crores), using a log-uniform-ish draw so we
        # get small and large tenders both represented.
        estimated_value = round(random.uniform(500_000, 50_000_000), 2)

        publish_date = _random_date(DATASET_START_DATE, DATASET_END_DATE - timedelta(days=60))
        window_days = random.randint(10, 45)
        submission_deadline = publish_date + timedelta(days=window_days)

        awarded_vendor_id = random.choice(vendor_ids)

        # Normal negotiation variance: awarded value typically lands
        # within +/-8% of the estimate, not wildly above it.
        awarded_value = round(estimated_value * random.uniform(0.92, 1.08), 2)

        tenders.append({
            "tender_reference": f"TND-{publish_date.year}-{i + 1:05d}",
            "title": f"{category} - {department} Procurement",
            "category": category,
            "region": region,
            "department": department,
            "estimated_value": estimated_value,
            "publish_date": publish_date.isoformat(),
            "submission_deadline": submission_deadline.isoformat(),
            "tender_window_days": window_days,
            "awarded_vendor_id": awarded_vendor_id,
            "awarded_value": awarded_value,
            "status": "Awarded",
            "is_synthetic_anomaly": False,
            "anomaly_type": None,
        })

    return tenders


def generate_bids_for_tender(tender: dict, vendor_ids: list[int],
                              bidder_count: int = None) -> list[dict]:
    """
    Generates bid records for a single clean tender.

    The winning bid always equals the tender's awarded_value. Losing
    bids are scattered realistically ABOVE the winning bid (since in
    most procurement processes the lowest valid bid wins), with
    healthy spread between them -- this natural spread is precisely
    what the Bid Clustering detector later contrasts anomalous,
    tightly-clustered bids against.

    Args:
        tender: A tender dict (must already include awarded_value and
            awarded_vendor_id).
        vendor_ids: Pool of vendor_id values eligible to bid.
        bidder_count: Number of bidders for this tender. If None, a
            realistic random count (3-7) is chosen.

    Returns:
        List of bid dicts (without bid_id or tender_id, which the
        caller attaches after the tender is inserted and has an ID).
    """
    if bidder_count is None:
        bidder_count = random.randint(3, 7)

    winning_vendor_id = tender["awarded_vendor_id"]
    awarded_value = tender["awarded_value"]

    # Pick losing bidders distinct from the winner.
    other_vendor_pool = [v for v in vendor_ids if v != winning_vendor_id]
    losing_vendor_ids = random.sample(
        other_vendor_pool, k=min(bidder_count - 1, len(other_vendor_pool))
    )

    bid_date = date.fromisoformat(tender["submission_deadline"]) - timedelta(
        days=random.randint(0, 3)
    )

    bids = [{
        "vendor_id": winning_vendor_id,
        "bid_amount": awarded_value,
        "bid_date": bid_date.isoformat(),
        "is_winning_bid": True,
    }]

    for vendor_id in losing_vendor_ids:
        # Losing bids spread meaningfully above the winning bid
        # (3% to 25% higher) -- natural, non-clustered variance.
        losing_amount = round(awarded_value * random.uniform(1.03, 1.25), 2)
        bids.append({
            "vendor_id": vendor_id,
            "bid_amount": losing_amount,
            "bid_date": bid_date.isoformat(),
            "is_winning_bid": False,
        })

    return bids


# ----------------------------------------------------------------------
# ANOMALY INJECTION (the 5% target patterns)
# ----------------------------------------------------------------------
#
# Each injector takes a slice of already-generated clean tenders and
# mutates them in place to embed one specific anomaly pattern, then
# regenerates that tender's bids to match. Splitting these into five
# small functions (rather than one large branching function) keeps
# each pattern independently readable, testable, and easy to tune.

def inject_vendor_concentration(tenders: list[dict], flagged_vendor_ids: list[int],
                                 count: int) -> None:
    """
    Pattern: Vendor Concentration.

    Forces a SINGLE vendor to win nearly all tenders within one
    region+category combination, simulating a vendor that wins far
    more often than competitive bidding would predict. With ~1000
    tenders spread across 6 regions x 10 categories, a region+category
    pair would normally see only a handful of tenders all year with
    wins spread across many of the 50 vendors -- concentrating most or
    all of a pair's wins onto one vendor makes that vendor's win share
    far above what chance would produce.

    Mutates `awarded_vendor_id`, `region`, and `category` only; leaves
    pricing and bid spread alone so this pattern stays isolated from
    Price Inflation / Bid Clustering signals.
    """
    # Split the count tenders into 2 separate region+category pairs,
    # each dominated by ONE vendor (not split across several), so the
    # concentration is unambiguous: e.g. 1 vendor winning 5 of 5
    # injected tenders in that pair, on top of whatever share of
    # ordinary tenders also happen to land in that same pair.
    half = count // 2
    pair_configs = [
        (random.choice(REGIONS), random.choice(CATEGORIES), flagged_vendor_ids[0], tenders[:half]),
        (random.choice(REGIONS), random.choice(CATEGORIES), flagged_vendor_ids[1], tenders[half:]),
    ]

    for region, category, vendor_id, tender_slice in pair_configs:
        for tender in tender_slice:
            tender["region"] = region
            tender["category"] = category
            tender["awarded_vendor_id"] = vendor_id
            tender["is_synthetic_anomaly"] = True
            tender["anomaly_type"] = "Vendor Concentration"
            # Awarded value stays within normal variance -- only the WIN
            # DISTRIBUTION is anomalous here, not the price.


def inject_bid_clustering(tenders: list[dict], count: int) -> None:
    """
    Pattern: Bid Clustering.

    Marks tenders for tight bid clustering. The actual bid amounts are
    generated later in generate_all_bids() by checking this flag --
    when present, all bids are placed within ~1-2% of each other
    instead of the normal 3-25% spread, simulating possible bid
    coordination between competing vendors.
    """
    selected = random.sample(tenders, k=count)
    for tender in selected:
        tender["is_synthetic_anomaly"] = True
        tender["anomaly_type"] = "Bid Clustering"


def inject_single_bidder(tenders: list[dict], count: int) -> None:
    """
    Pattern: Single Bidder.

    Marks tenders to receive exactly one bid (the winning bid only),
    simulating a tender that effectively had no real competition.
    """
    selected = random.sample(tenders, k=count)
    for tender in selected:
        tender["is_synthetic_anomaly"] = True
        tender["anomaly_type"] = "Single Bidder"


def inject_short_tender_window(tenders: list[dict], count: int) -> None:
    """
    Pattern: Short Tender Window.

    Compresses the gap between publish_date and submission_deadline to
    1-2 days, far below the normal 10-45 day window, simulating a
    tender that gave the market little real opportunity to compete.
    """
    selected = random.sample(tenders, k=count)
    for tender in selected:
        publish_date = date.fromisoformat(tender["publish_date"])
        short_window = random.randint(1, 2)
        new_deadline = publish_date + timedelta(days=short_window)

        tender["submission_deadline"] = new_deadline.isoformat()
        tender["tender_window_days"] = short_window
        tender["is_synthetic_anomaly"] = True
        tender["anomaly_type"] = "Short Tender Window"


def inject_price_inflation(tenders: list[dict], count: int) -> None:
    """
    Pattern: Price Inflation.

    Inflates the awarded_value to 40-70% above the estimated_value,
    far beyond the normal +/-8% negotiation variance, simulating a
    tender awarded at a price well outside reasonable market
    justification relative to the original estimate.
    """
    selected = random.sample(tenders, k=count)
    for tender in selected:
        inflation_factor = random.uniform(1.40, 1.70)
        tender["awarded_value"] = round(tender["estimated_value"] * inflation_factor, 2)
        tender["is_synthetic_anomaly"] = True
        tender["anomaly_type"] = "Price Inflation"


# ----------------------------------------------------------------------
# BID GENERATION FOR THE FULL DATASET (clean + anomalous aware)
# ----------------------------------------------------------------------

def generate_all_bids(tenders_with_ids: list[dict], vendor_ids: list[int]) -> list[dict]:
    """
    Generates bids for every tender in the dataset, respecting each
    tender's anomaly_type where applicable:

        - "Single Bidder"   -> exactly one bid (the winner only).
        - "Bid Clustering"  -> 4-6 bids tightly packed within ~1-2%
                                of the winning amount.
        - all other tenders -> normal generate_bids_for_tender() logic
                                (3-7 bidders, natural 3-25% spread).

    Args:
        tenders_with_ids: Tenders that have already been inserted into
            the DB and therefore have a real `tender_id` populated.
        vendor_ids: Full pool of vendor_id values eligible to bid.

    Returns:
        Flat list of bid dicts, each including its parent `tender_id`,
        ready for bulk insertion.
    """
    all_bids = []

    for tender in tenders_with_ids:
        anomaly_type = tender.get("anomaly_type")

        if anomaly_type == "Single Bidder":
            bids = [{
                "vendor_id": tender["awarded_vendor_id"],
                "bid_amount": tender["awarded_value"],
                "bid_date": tender["submission_deadline"],
                "is_winning_bid": True,
            }]

        elif anomaly_type == "Bid Clustering":
            winning_vendor_id = tender["awarded_vendor_id"]
            awarded_value = tender["awarded_value"]
            other_pool = [v for v in vendor_ids if v != winning_vendor_id]
            bidder_count = random.randint(4, 6)
            losing_vendor_ids = random.sample(
                other_pool, k=min(bidder_count - 1, len(other_pool))
            )

            bid_date = date.fromisoformat(tender["submission_deadline"]) - timedelta(
                days=random.randint(0, 2)
            )

            bids = [{
                "vendor_id": winning_vendor_id,
                "bid_amount": awarded_value,
                "bid_date": bid_date.isoformat(),
                "is_winning_bid": True,
            }]
            for vendor_id in losing_vendor_ids:
                # Tight cluster: within 0.5%-2% of the winning bid,
                # versus the normal 3%-25% spread used elsewhere.
                clustered_amount = round(awarded_value * random.uniform(1.005, 1.02), 2)
                bids.append({
                    "vendor_id": vendor_id,
                    "bid_amount": clustered_amount,
                    "bid_date": bid_date.isoformat(),
                    "is_winning_bid": False,
                })

        else:
            bids = generate_bids_for_tender(tender, vendor_ids)

        for bid in bids:
            bid["tender_id"] = tender["tender_id"]
        all_bids.extend(bids)

    return all_bids


# ----------------------------------------------------------------------
# ORCHESTRATION
# ----------------------------------------------------------------------

def build_dataset() -> tuple[list[dict], list[dict]]:
    """
    Builds the full in-memory dataset (vendors and tenders are
    inserted to get real IDs first; bids are generated afterward since
    they depend on tender_id/vendor_id foreign keys).

    Returns:
        (vendor_records, tender_records) -- both already containing
        their real auto-assigned vendor_id / tender_id after insertion,
        for convenience when this function is called from
        seed_database() below. Bids are inserted separately by the
        caller since they depend on the full tender list.
    """
    # 1. Vendors
    vendor_records = generate_vendors(TOTAL_VENDORS)
    vendor_insert_sql = """
        INSERT INTO vendors
            (vendor_name, registration_number, region,
             category_specialization, date_registered, is_flagged_entity)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    for vendor in vendor_records:
        new_id = execute_write(
            vendor_insert_sql,
            (
                vendor["vendor_name"], vendor["registration_number"],
                vendor["region"], vendor["category_specialization"],
                vendor["date_registered"], vendor["is_flagged_entity"],
            ),
        )
        vendor["vendor_id"] = new_id

    vendor_ids = [v["vendor_id"] for v in vendor_records]
    flagged_vendor_ids = [v["vendor_id"] for v in vendor_records if v["is_flagged_entity"]]

    # 2. Clean tenders (95% baseline)
    clean_count = TOTAL_TENDERS - TOTAL_ANOMALOUS_TENDERS
    tenders = generate_clean_tenders(vendor_ids, clean_count)

    # 3. Anomalous tenders: generate as more clean tenders first, then
    # mutate slices of them in place. This guarantees every anomalous
    # tender still has realistic baseline values for every field that
    # particular anomaly type doesn't deliberately distort.
    anomalous_tenders = generate_clean_tenders(
        vendor_ids, TOTAL_ANOMALOUS_TENDERS, start_index=clean_count
    )

    # Split the 50 anomalous tenders evenly across the 5 patterns (10 each).
    per_pattern = TOTAL_ANOMALOUS_TENDERS // len(ANOMALY_TYPES)
    chunks = [anomalous_tenders[i:i + per_pattern] for i in range(0, len(anomalous_tenders), per_pattern)]

    inject_vendor_concentration(chunks[0], flagged_vendor_ids, per_pattern)
    inject_bid_clustering(chunks[1], per_pattern)
    inject_single_bidder(chunks[2], per_pattern)
    inject_short_tender_window(chunks[3], per_pattern)
    inject_price_inflation(chunks[4], per_pattern)

    tenders.extend(anomalous_tenders)
    random.shuffle(tenders)  # avoid anomalies clustering at the end of tender_reference ordering

    # 4. Insert tenders and capture real tender_id values.
    tender_insert_sql = """
        INSERT INTO tenders
            (tender_reference, title, category, region, department,
             estimated_value, publish_date, submission_deadline,
             tender_window_days, awarded_vendor_id, awarded_value,
             status, is_synthetic_anomaly, anomaly_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    for tender in tenders:
        new_id = execute_write(
            tender_insert_sql,
            (
                tender["tender_reference"], tender["title"], tender["category"],
                tender["region"], tender["department"], tender["estimated_value"],
                tender["publish_date"], tender["submission_deadline"],
                tender["tender_window_days"], tender["awarded_vendor_id"],
                tender["awarded_value"], tender["status"],
                tender["is_synthetic_anomaly"], tender["anomaly_type"],
            ),
        )
        tender["tender_id"] = new_id

    return vendor_records, tenders


def seed_database(drop_existing: bool = True) -> None:
    """
    Main entrypoint: initializes the schema and populates it with a
    full synthetic dataset (vendors, tenders, bids).

    Args:
        drop_existing: If True (default), wipes any existing tables
            first so this script always produces a clean, reproducible
            dataset rather than accumulating duplicate data on reruns.
    """
    print("Initializing database schema...")
    initialize_database(drop_existing=drop_existing)

    print(f"Generating {TOTAL_VENDORS} vendors and {TOTAL_TENDERS} tenders "
          f"({TOTAL_ANOMALOUS_TENDERS} anomalous, {TOTAL_TENDERS - TOTAL_ANOMALOUS_TENDERS} clean)...")
    vendor_records, tender_records = build_dataset()
    vendor_ids = [v["vendor_id"] for v in vendor_records]

    print("Generating bids for all tenders...")
    bid_records = generate_all_bids(tender_records, vendor_ids)

    bid_insert_sql = """
        INSERT INTO bids (tender_id, vendor_id, bid_amount, bid_date, is_winning_bid)
        VALUES (?, ?, ?, ?, ?)
    """
    bid_rows = [
        (b["tender_id"], b["vendor_id"], b["bid_amount"], b["bid_date"], b["is_winning_bid"])
        for b in bid_records
    ]
    execute_many(bid_insert_sql, bid_rows)

    print(f"Seed complete: {len(vendor_records)} vendors, "
          f"{len(tender_records)} tenders, {len(bid_records)} bids inserted.")

    anomaly_breakdown = {atype: 0 for atype in ANOMALY_TYPES}
    for tender in tender_records:
        if tender["anomaly_type"]:
            anomaly_breakdown[tender["anomaly_type"]] += 1
    print("Anomaly breakdown:", anomaly_breakdown)


if __name__ == "__main__":
    # Allows the dataset to be (re)built directly via:
    #     python -m database.seed_data
    seed_database(drop_existing=True)
