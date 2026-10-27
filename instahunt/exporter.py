"""
Export and Sheet Synchronization Module for InstaHunt.
Imports existing client profiles from StormShadow.xlsx, formats new qualified rows,
appends them to the spreadsheet, and exports CSV and audit reports.
"""

import csv
import secrets
from pathlib import Path
from typing import Dict, List, Optional
import openpyxl

from instahunt.config import DEFAULT_DB_PATH, DEFAULT_OUTPUT_DIR, DEFAULT_SHEET_PATH
from instahunt.db import enqueue_profiles, get_qualified_profiles, get_stats, upsert_profile


def extract_username_from_url(url: str) -> Optional[str]:
    """Extract clean Instagram handle from link."""
    clean = url.strip()
    if not clean or "instagram.com" not in clean:
        return None
    # Strip protocol and domain
    parts = clean.split("instagram.com/")[-1].split("?")[0].split("/")
    candidate = parts[0].strip()
    if candidate.lower() in ("p", "reel", "reels", "stories", "explore") and len(parts) > 1:
        return None
    return candidate.lower() if candidate else None


def generate_stkn() -> str:
    """Generate mock 32-char base64-like tracking token to match client format."""
    return secrets.token_urlsafe(24)


class SheetExporter:
    def __init__(self, sheet_path: Path = DEFAULT_SHEET_PATH, db_path: Path = DEFAULT_DB_PATH):
        self.sheet_path = Path(sheet_path)
        self.db_path = Path(db_path)

    def import_seed_profiles(self) -> Dict[str, int]:
        """
        Import existing profiles from StormShadow.xlsx into SQLite.
        Marks existing Sheet1 profiles as 'seed_existing' so we never duplicate them.
        Imports 'Example Profiles' (working ones) into discovery queue at priority 50.
        """
        if not self.sheet_path.exists():
            raise FileNotFoundError(f"Spreadsheet not found at {self.sheet_path}")

        wb = openpyxl.load_workbook(self.sheet_path, data_only=True)
        stats = {"sheet1_imported": 0, "examples_working_imported": 0, "examples_nonworking_imported": 0}

        # 1. Process Sheet1 (Existing Links)
        if "Sheet1" in wb.sheetnames:
            ws = wb["Sheet1"]
            sheet1_handles = []
            for row in ws.iter_rows(min_row=2, max_col=1, values_only=True):
                val = row[0]
                if val and isinstance(val, str) and "instagram.com" in val:
                    h = extract_username_from_url(val)
                    if h:
                        sheet1_handles.append(h)
                        # Upsert as already existing in profiles table so we never add again
                        upsert_profile({
                            "username": h,
                            "full_name": "Client Existing Record",
                            "biography": "Imported from StormShadow.xlsx Sheet1",
                            "status": "pending",
                            "evidence": "Existing record in client sheet",
                        }, db_path=self.db_path)

            stats["sheet1_imported"] = len(sheet1_handles)

        # 2. Process 'Example Profiles'
        if "Example Profiles" in wb.sheetnames:
            ws_ex = wb["Example Profiles"]
            working_seeds = []
            nonworking_seeds = []

            is_working_section = False
            is_nonworking_section = False

            for row in ws_ex.iter_rows(values_only=True):
                text_col0 = str(row[0] or "").strip()
                if "Profiles that work" in text_col0:
                    is_working_section = True
                    is_nonworking_section = False
                    continue
                elif "Profiles that DONT work" in text_col0:
                    is_working_section = False
                    is_nonworking_section = True
                    continue

                val = row[0]
                if val and isinstance(val, str) and "instagram.com" in val:
                    h = extract_username_from_url(val)
                    if h:
                        if is_working_section:
                            working_seeds.append(h)
                        elif is_nonworking_section:
                            nonworking_seeds.append(h)

            if working_seeds:
                # Working seeds get priority 50 to spider outward from them first!
                enqueue_profiles(working_seeds, source="seed_example_working", priority=50, force=True, db_path=self.db_path)
                stats["examples_working_imported"] = len(working_seeds)

            if nonworking_seeds:
                for nh in nonworking_seeds:
                    upsert_profile({
                        "username": nh,
                        "full_name": "Client Nonworking Example",
                        "status": "rejected",
                        "rejection_reason": "client_example_negative",
                        "evidence": "Marked as non-working in client Example Profiles tab",
                    }, db_path=self.db_path)
                stats["examples_nonworking_imported"] = len(nonworking_seeds)

        return stats

    def append_qualified_to_sheet(
        self,
        output_path: Optional[Path] = None,
        use_tracking_token: bool = True,
    ) -> int:
        """
        Append all qualified profiles from SQLite into Sheet1 of the Excel workbook.
        """
        target_path = Path(output_path) if output_path else self.sheet_path
        if not target_path.exists():
            raise FileNotFoundError(f"Workbook not found at {target_path}")

        wb = openpyxl.load_workbook(target_path)
        ws = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb.active

        # Read already present links to ensure zero duplicates
        existing_handles = set()
        for row in ws.iter_rows(min_row=1, max_col=1, values_only=True):
            val = row[0]
            if val and isinstance(val, str) and "instagram.com" in val:
                h = extract_username_from_url(val)
                if h:
                    existing_handles.add(h)

        qualified_profiles = get_qualified_profiles(db_path=self.db_path)
        added_count = 0

        for p in qualified_profiles:
            u = p["username"].lower()
            if u not in existing_handles:
                stkn = generate_stkn()
                if use_tracking_token:
                    url = f"https://www.instagram.com/{u}?stkn={stkn}"
                else:
                    url = f"https://www.instagram.com/{u}/"

                ws.append([url])
                existing_handles.add(u)
                added_count += 1

        target_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(target_path)
        return added_count

    def export_to_csv(self, output_path: Optional[Path] = None) -> Path:
        """Export all qualified profiles to a detailed CSV with audit evidence."""
        out_file = output_path or (DEFAULT_OUTPUT_DIR / "qualified_creators.csv")
        out_file.parent.mkdir(parents=True, exist_ok=True)

        profiles = get_qualified_profiles(db_path=self.db_path)
        fieldnames = [
            "username",
            "full_name",
            "followers_count",
            "avg_comments",
            "detected_city",
            "city_tier",
            "evidence",
            "profile_url",
            "formatted_client_url",
        ]

        with open(out_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for p in profiles:
                u = p["username"].lower()
                stkn = generate_stkn()
                writer.writerow({
                    "username": u,
                    "full_name": p.get("full_name", ""),
                    "followers_count": p.get("followers_count", 0),
                    "avg_comments": f"{p.get('avg_comments', 0.0):.1f}",
                    "detected_city": p.get("detected_city", ""),
                    "city_tier": p.get("city_tier", ""),
                    "evidence": p.get("evidence", ""),
                    "profile_url": f"https://www.instagram.com/{u}/",
                    "formatted_client_url": f"https://www.instagram.com/{u}?stkn={stkn}",
                })

        return out_file

    def generate_markdown_report(self, output_path: Optional[Path] = None) -> Path:
        """Generate markdown audit report summarizing pipeline performance."""
        out_file = output_path or (DEFAULT_OUTPUT_DIR / "instahunt_audit_report.md")
        out_file.parent.mkdir(parents=True, exist_ok=True)

        stats = get_stats(db_path=self.db_path)
        qualified = get_qualified_profiles(db_path=self.db_path)

        lines = [
            "# InstaHunt: Automated Creator Discovery Audit Report",
            "",
            "## 1. Funnel Performance Overview",
            f"- **Total Profiles Evaluated:** {stats['total_profiles']}",
            f"- **Qualified Tier 2/3 Creators:** {stats['qualified']}",
            f"- **Rejected Profiles:** {stats['rejected']}",
            f"- **Pending in Discovery Queue:** {stats['pending_queue']}",
            "",
            "## 2. Rejection Breakdown",
        ]

        for reason, count in sorted(stats["rejection_reasons"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- `{reason}`: {count}")

        lines.extend([
            "",
            "## 3. Verified Tier 2 & Tier 3 Skincare Creators",
            "| Username | Full Name | Followers | Avg Comments | City | Tier | Evidence |",
            "|---|---|---|---|---|---|---|",
        ])

        for p in qualified:
            lines.append(
                f"| [@{p['username']}](https://www.instagram.com/{p['username']}/) | "
                f"{p.get('full_name', '')} | {p.get('followers_count', 0):,} | "
                f"{p.get('avg_comments', 0.0):.1f} | {p.get('detected_city', '')} | "
                f"{p.get('city_tier', '')} | {p.get('evidence', '')} |"
            )

        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return out_file
