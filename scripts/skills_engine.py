#!/usr/bin/env python3
"""
InstaHunt Skills Engine — Intelligent Profile Discovery & Audit Pipeline.

Replaces the broken rule-based continuous_learning_engine.py.
Uses skills-based discovery (agent-reach web search) instead of HTTP dork bots.

Architecture:
  Phase 1: SkillsDiscoverer — find real handles via agent-reach web search
  Phase 2: SkillsAuditor   — 5-gate audit with live web grounding
  Phase 3: SheetExporter   — write verified profiles to Skin care creators.xlsx
  Phase 4: Feedback Loop   — log audit results, tune city priority

Usage:
  cd /tmp/workspace/instahunt
  venv/bin/python3 scripts/skills_engine.py \\
      --target 50 \\
      --cities "Nashik,Nagpur,Bhopal,Lucknow,Patna" \\
      --sheet data/Skin\\ care\\ creators.xlsx \\
      --start-row 461

  # Or run full city sweep:
  venv/bin/python3 scripts/skills_engine.py --target 80
"""

import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

# Ensure instahunt package is importable from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Environment setup ──────────────────────────────────────────────────────────
AGENT_REACH_BIN = os.path.expanduser("~/.local/bin/agent-reach")
os.environ["PATH"] = f"{os.path.expanduser('~/.local/bin')}:{os.environ.get('PATH', '')}"

# ── Imports from instahunt package ─────────────────────────────────────────────
from instahunt.skills_discoverer import (
    DiscoveredProfile,
    SkillsDiscoverer,
    INDIAN_TIER2_TIER3_CITIES,
)
from instahunt.skills_auditor import AuditVerdict, SkillsAuditor
from instahunt.exporter import SheetExporter           # existing exporter works fine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("skills_engine")

# ── Paths ──────────────────────────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

DEFAULT_SHEET = DATA_DIR / "Skin care creators.xlsx"
DEFAULT_AUDIT_LOG = DATA_DIR / "skills_engine_audit.csv"
DEFAULT_DISCOVERY_LOG = DATA_DIR / "skills_engine_discoveries.json"


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_existing_handles(sheet_path: Path) -> Set[str]:
    """
    Read the existing sheet to collect all handles already in it.
    Prevents duplicates when adding new rows.
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(sheet_path))
        ws = wb.active
        handles = set()
        for row in ws.iter_rows(min_row=2, max_col=1, values_only=True):
            cell_val = row[0]
            if not cell_val:
                continue
            # Handle may be a hyperlink string like https://www.instagram.com/handle
            handle = str(cell_val).strip().rstrip("/").split("/")[-1].lstrip("@").lower()
            if handle:
                handles.add(handle)
        logger.info(f"Loaded {len(handles)} existing handles from sheet")
        return handles
    except Exception as e:
        logger.warning(f"Could not read existing sheet: {e}")
        return set()


def find_next_empty_row(sheet_path: Path, min_start_row: int = 451) -> int:
    """
    Find the first empty row at or after min_start_row (Column A is empty).
    Defaults to 451 to protect the legacy block (rows 1-450).
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(sheet_path))
        ws = wb.active
        for row_idx in range(min_start_row, ws.max_row + 2):
            cell = ws.cell(row=row_idx, column=1)
            if not cell.value:
                return row_idx
        return ws.max_row + 1
    except Exception as e:
        logger.warning(f"Could not determine next empty row: {e}")
        return 461  # Safe default


def write_verified_to_sheet(
    sheet_path: Path,
    verdicts: List[AuditVerdict],
    start_row: int,
) -> int:
    """
    Write verified profiles into the sheet starting at start_row.
    Returns the number of rows written.
    Uses openpyxl directly for precise formatting control.
    Column A: hyperlink → https://www.instagram.com/<handle>
    Font: Arial 10pt, #1155CC, single underline (matches existing sheet style).
    All other columns remain empty.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter

        wb = openpyxl.load_workbook(str(sheet_path))
        ws = wb.active

        link_font = Font(
            name="Arial",
            size=10,
            color="1155CC",
            underline="single",
        )

        written = 0
        for i, v in enumerate(verdicts):
            row_idx = start_row + i
            handle_clean = v.handle.lstrip("@").lower()
            url = f"https://www.instagram.com/{handle_clean}/reels/"

            cell = ws.cell(row=row_idx, column=1)
            cell.value = url
            cell.hyperlink = url
            cell.font = link_font

            written += 1

        # Preserve metadata — keep Creator: Excel
        wb.properties.creator = "Excel"
        wb.properties.lastModifiedBy = "Excel"
        wb.save(str(sheet_path))
        logger.info(f"Wrote {written} new profiles to sheet starting at row {start_row}")
        return written

    except Exception as e:
        logger.error(f"Failed to write to sheet: {e}")
        return 0


def save_audit_log(
    verdicts_passed: List[AuditVerdict],
    verdicts_rejected: List[AuditVerdict],
    audit_log_path: Path,
) -> None:
    """Append audit results to CSV log."""
    fieldnames = [
        "handle", "passed", "overall_score", "city", "city_tier",
        "is_tier2_tier3", "is_skincare_confirmed", "followers",
        "engagement_rate", "web_grounded", "rejection_reason",
        "gate_scores", "source_url", "audit_notes", "timestamp",
    ]
    ts = datetime.now(timezone.utc).isoformat()
    rows = []
    for v in verdicts_passed + verdicts_rejected:
        rows.append({
            "handle": v.handle,
            "passed": v.passed,
            "overall_score": v.overall_score,
            "city": v.city or "",
            "city_tier": v.city_tier or "",
            "is_tier2_tier3": v.is_tier2_tier3,
            "is_skincare_confirmed": v.is_skincare_confirmed,
            "followers": v.followers or "",
            "engagement_rate": v.engagement_rate or "",
            "web_grounded": v.web_grounded,
            "rejection_reason": v.rejection_reason or "",
            "gate_scores": json.dumps(v.gate_scores),
            "source_url": v.source_url or "",
            "audit_notes": v.audit_notes[:200],
            "timestamp": ts,
        })

    write_header = not audit_log_path.exists()
    with open(audit_log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
    logger.info(f"Audit log updated: {audit_log_path}")


def save_discovery_log(profiles: List[DiscoveredProfile], log_path: Path) -> None:
    """Save raw discovery results as JSON for inspection."""
    data = []
    for p in profiles:
        data.append({
            "handle": p.handle,
            "name": p.name,
            "city": p.city,
            "state": p.state,
            "city_tier": p.city_tier,
            "followers": p.followers,
            "engagement_rate": p.engagement_rate,
            "is_skincare_confirmed": p.is_skincare_confirmed,
            "is_tier2_tier3": p.is_tier2_tier3,
            "source_url": p.source_url,
            "discovery_query": p.discovery_query,
            "evidence_snippet": p.evidence_snippet[:400],
        })
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Discovery log saved: {log_path}")


# ── Main Engine ────────────────────────────────────────────────────────────────

def run_engine(
    target_profiles: int = 50,
    target_cities: Optional[List[str]] = None,
    sheet_path: Path = DEFAULT_SHEET,
    start_row: Optional[int] = None,
    dry_run: bool = False,
    require_web_grounding: bool = True,
) -> Dict:
    """
    Full skills-based pipeline: Discover → Audit → Write to sheet.

    Returns a summary dict with counts and stats.
    """
    print("\n" + "═" * 65)
    print("  InstaHunt Skills Engine  — Intelligent Discovery Pipeline")
    print("═" * 65)
    print(f"  Target: {target_profiles} verified profiles")
    print(f"  Sheet:  {sheet_path}")
    print(f"  Cities: {len(target_cities) if target_cities else 'ALL Tier 2/3'}")
    print(f"  Dry run: {dry_run}")
    print("═" * 65 + "\n")

    # ── Step 0: Load existing handles to prevent duplicates ────────────────
    existing_handles: Set[str] = set()
    if sheet_path.exists():
        existing_handles = load_existing_handles(sheet_path)
    print(f"[0] {len(existing_handles)} handles already in sheet (dedupe active)\n")

    # ── Step 1: Discover raw candidates ────────────────────────────────────
    print("[1] DISCOVERY PHASE — agent-reach web search")
    print("-" * 50)
    cities = target_cities or list(INDIAN_TIER2_TIER3_CITIES.keys())
    discoverer = SkillsDiscoverer(
        target_cities=cities,
        max_queries_per_city=2,
        max_profiles=target_profiles,
        seen_handles=existing_handles,
    )
    raw_profiles = discoverer.discover(verbose=True)
    print(f"\n  → {len(raw_profiles)} raw candidates discovered\n")

    if not raw_profiles:
        print("  ⚠ No profiles discovered. Check agent-reach connectivity.")
        return {"discovered": 0, "passed": 0, "rejected": 0, "written": 0}

    # Save raw discovery log
    save_discovery_log(raw_profiles, DEFAULT_DISCOVERY_LOG)

    # ── Step 2: Audit each profile through 5 gates ─────────────────────────
    print("[2] AUDIT PHASE — 5-gate skills audit")
    print("-" * 50)
    auditor = SkillsAuditor(
        min_followers=3_000,
        max_followers=500_000,
        min_engagement_rate=1.5,
        require_web_grounding=require_web_grounding,
    )
    passed, rejected = auditor.audit_batch(raw_profiles, verbose=True)

    print(f"\n  → {len(passed)} PASSED | {len(rejected)} REJECTED")
    print(f"  → Pass rate: {len(passed)/max(1,len(raw_profiles))*100:.1f}%\n")

    # Save audit log
    save_audit_log(passed, rejected, DEFAULT_AUDIT_LOG)

    # Limit to target count
    to_write = passed[:target_profiles]

    # ── Step 3: Write to sheet ─────────────────────────────────────────────
    written = 0
    if not dry_run and to_write:
        print(f"[3] SHEET WRITE PHASE — writing {len(to_write)} verified profiles")
        print("-" * 50)

        if not sheet_path.exists():
            print(f"  ⚠ Sheet not found at {sheet_path} — skipping write")
        else:
            # Determine start row
            if start_row is None:
                start_row = find_next_empty_row(sheet_path)
            print(f"  Writing from row {start_row}…")
            written = write_verified_to_sheet(sheet_path, to_write, start_row)
            print(f"  ✓ {written} rows written to sheet\n")
    elif dry_run:
        print(f"[3] DRY RUN — would write {len(to_write)} profiles (skipped)\n")

    # ── Step 4: Summary Report ─────────────────────────────────────────────
    print("[4] SESSION SUMMARY")
    print("═" * 65)
    print(f"  Discovered (raw):    {len(raw_profiles)}")
    print(f"  Passed audit:        {len(passed)}")
    print(f"  Rejected:            {len(rejected)}")
    print(f"  Written to sheet:    {written}")
    print(f"  Audit log:           {DEFAULT_AUDIT_LOG}")
    print(f"  Discovery log:       {DEFAULT_DISCOVERY_LOG}")

    if passed:
        print(f"\n  ✅ Verified profiles added:")
        for v in to_write:
            print(f"     @{v.handle:<30} {v.city:<18} [{v.city_tier}]  score={v.overall_score:.2f}")

    print("═" * 65 + "\n")

    return {
        "discovered": len(raw_profiles),
        "passed": len(passed),
        "rejected": len(rejected),
        "written": written,
        "profiles": [v.handle for v in to_write],
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="InstaHunt Skills Engine — skills-based discovery pipeline"
    )
    parser.add_argument(
        "--target", type=int, default=50,
        help="Target number of verified profiles to add (default: 50)"
    )
    parser.add_argument(
        "--cities", type=str, default="",
        help="Comma-separated list of target cities (default: all Tier 2/3)"
    )
    parser.add_argument(
        "--sheet", type=str, default=str(DEFAULT_SHEET),
        help=f"Path to the Skin care creators.xlsx file (default: {DEFAULT_SHEET})"
    )
    parser.add_argument(
        "--start-row", type=int, default=None,
        help="Row number to start writing from (default: auto-detect next empty row)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Discover and audit but don't write to sheet"
    )
    parser.add_argument(
        "--no-grounding", action="store_true",
        help="Skip web grounding check (faster, less accurate)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    cities = [c.strip() for c in args.cities.split(",") if c.strip()] or None

    result = run_engine(
        target_profiles=args.target,
        target_cities=cities,
        sheet_path=Path(args.sheet),
        start_row=args.start_row,
        dry_run=args.dry_run,
        require_web_grounding=not args.no_grounding,
    )

    sys.exit(0 if result["passed"] > 0 else 1)
