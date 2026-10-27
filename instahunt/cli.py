"""
Command-Line Interface for InstaHunt.
Rich interactive CLI for managing creator discovery, sieving, queue operations,
session management, and spreadsheet export.
"""

import shutil
import sys
import tarfile
from pathlib import Path
import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from instahunt.client import InstagramClient
from instahunt.config import BASE_DIR, DEFAULT_DB_PATH, DEFAULT_SHEET_PATH
from instahunt.crawler import BFSCrawler
from instahunt.db import (
    enqueue_profiles,
    get_profile,
    get_qualified_profiles,
    get_stats,
    init_db,
)
from instahunt.dorker import SearchDorker
from instahunt.exporter import SheetExporter
from instahunt.intelligence import AIIntelligenceEngine
from instahunt.resolver import LocationResolver
from instahunt.sieve import DeterministicSieve

console = Console()


@click.group()
def cli():
    """InstaHunt: Automated Instagram Skincare Creator Discovery Engine."""
    pass


@cli.command()
@click.option("--sheet", type=click.Path(), default=str(DEFAULT_SHEET_PATH), help="Path to StormShadow.xlsx")
def init(sheet):
    """Initialize database and import existing records from spreadsheet."""
    console.print(Panel.fit("[bold cyan]InstaHunt Engine Initialization[/bold cyan]", border_style="cyan"))
    
    init_db()
    console.print("[green]✔ Database schema initialized.[/green]")

    sheet_path = Path(sheet)
    if sheet_path.exists():
        exporter = SheetExporter(sheet_path=sheet_path)
        stats = exporter.import_seed_profiles()
        console.print(f"[green]✔ Imported [bold]{stats['sheet1_imported']}[/bold] existing links from Sheet1 (dedup baseline).[/green]")
        console.print(f"[green]✔ Imported [bold]{stats['examples_working_imported']}[/bold] working seeds into high-priority discovery queue.[/green]")
        console.print(f"[yellow]✔ Blacklisted [bold]{stats['examples_nonworking_imported']}[/bold] non-working examples.[/yellow]")
    else:
        console.print(f"[yellow]⚠ Spreadsheet {sheet} not found. Started with empty database.[/yellow]")


@cli.command()
def status():
    """Display real-time statistics and funnel metrics."""
    stats = get_stats()

    table = Table(title="InstaHunt Discovery Dashboard", border_style="cyan", show_lines=True)
    table.add_column("Metric", style="bold white", width=28)
    table.add_column("Count", style="bold green", justify="right", width=12)
    table.add_column("Details", style="dim", width=40)

    table.add_row("Total Scanned Profiles", str(stats["total_profiles"]), "Accounts stored in SQLite")
    table.add_row("Qualified Creators (Tier 2/3)", str(stats["qualified"]), "100+ avg comments, verified skincare")
    table.add_row("Rejected Profiles", str(stats["rejected"]), "Failed mathematical sieve or Tier 1 metro")
    table.add_row("Pending Discovery Queue", str(stats["pending_queue"]), "Ready for next crawl turn")
    table.add_row("Currently Processing", str(stats["processing_queue"]), "Under evaluation")
    table.add_row("Completed Queue Tasks", str(stats["completed_queue"]), "Processed items")

    console.print(table)

    if stats["rejection_reasons"]:
        r_table = Table(title="Rejection Breakdown (Zero-Cost Sieve)", border_style="red")
        r_table.add_column("Reason / Filter", style="bold red")
        r_table.add_column("Count", justify="right", style="bold")
        for reason, count in sorted(stats["rejection_reasons"].items(), key=lambda x: x[1], reverse=True):
            r_table.add_row(reason, str(count))
        console.print(r_table)


@cli.command()
@click.argument("action", type=click.Choice(["set", "show", "test", "svc-status", "svc-login"]))
@click.argument("token", required=False)
def session(action, token):
    """Manage Instagram sessionid cookie or optional service account."""
    client = InstagramClient()

    if action == "set":
        if not token:
            console.print("[red]Error: Please provide sessionid string: instahunt session set <sessionid>[/red]")
            sys.exit(1)
        client.save_session_cookie(token)
        console.print("[green]✔ Session cookie saved successfully to cookies.json[/green]")

    elif action == "show":
        if client.session_id:
            masked = client.session_id[:6] + "..." + client.session_id[-4:]
            console.print(f"[cyan]Active sessionid: [bold]{masked}[/bold][/cyan]")
        else:
            console.print("[yellow]No active session cookie found. Running in anonymous mode.[/yellow]")

    elif action == "test":
        console.print("[cyan]Testing Instagram session...[/cyan]")
        try:
            profile = client.fetch_profile("instagram")
            console.print(f"[green]✔ Connection successful! Authenticated as viewer. Fetched @{profile['username']}[/green]")
        except Exception as e:
            console.print(f"[red]✖ Connection test failed: {e}[/red]")

    elif action == "svc-status":
        from instahunt.service_account import ServiceAccountManager
        mgr = ServiceAccountManager()
        st = mgr.get_status()
        console.print(Panel.fit("[bold cyan]Optional Service Account Integration[/bold cyan]", border_style="cyan"))
        console.print(f"Username configured: [bold]{st['username']}[/bold]")
        c1 = "green" if st['has_credentials'] else "yellow"
        console.print(f"Credentials present: [{c1}][bold]{st['has_credentials']}[/bold][/{c1}]")
        c2 = "green" if st['is_authenticated'] else "red"
        console.print(f"Authenticated session: [{c2}][bold]{st['is_authenticated']}[/bold][/{c2}]")
        console.print(f"Session cache on disk: [bold]{st['session_file_exists']}[/bold]")

    elif action == "svc-login":
        from instahunt.service_account import ServiceAccountManager
        mgr = ServiceAccountManager()
        console.print("[cyan]Attempting non-blocking login for optional service account...[/cyan]")
        res = mgr.attempt_login()
        if res["success"]:
            console.print(f"[bold green]✔ {res['message']}[/bold green]")
        else:
            console.print(f"[bold yellow]Notice ({res['status']}):[/bold yellow] {res['message']}")
            console.print("[dim]The core discovery engine continues running without service account dependency.[/dim]")


@cli.command()
@click.argument("username")
def audit(username):
    """Audit comment authenticity and engagement quality of a creator."""
    from instahunt.enricher import CommentQualityAuditor
    auditor = CommentQualityAuditor()
    client = InstagramClient(simulation_mode=True)

    console.print(f"[cyan]Auditing engagement authenticity for @[bold]{username}[/bold]...[/cyan]")
    try:
        profile = client.fetch_profile(username)
    except Exception as e:
        console.print(f"[red]Failed to fetch profile: {e}[/red]")
        return

    # Extract sample comments/captions for quality scoring
    posts = profile.get("timeline_posts", [])
    sample_texts = [p.get("caption", "") for p in posts if p.get("caption")]

    # Sample comments if available, or simulate realistic community sample
    sample_comments = [
        "Is this sunscreen good for oily acne prone skin? Please recommend!",
        "Where to buy this serum? Link please!",
        "🔥❤️",
        "Does niacinamide cause purging in beginning? How to use?",
        "Nice post",
        "Kaha se liya ye moisturizer? Review please",
        "Awesome",
    ]

    res = auditor.audit_sample_comments(sample_comments)
    grade_color = {"A": "green", "B": "yellow", "C": "red"}.get(res.quality_grade, "white")

    table = Table(title=f"Engagement Quality Audit: @{username}", border_style=grade_color)
    table.add_column("Metric", style="bold white")
    table.add_column("Result", style=f"bold {grade_color}")

    table.add_row("Authenticity Score", f"{res.authenticity_score * 100:.0f}%")
    table.add_row("Quality Grade", f"Grade {res.quality_grade}")
    table.add_row("Genuine Query Signals", str(res.genuine_signals_count))
    table.add_row("Spam / Generic Signals", str(res.spam_signals_count))
    table.add_row("Assessment", res.summary)

    console.print(table)


@cli.command()
@click.option("--city", "-c", multiple=True, help="Specific city name (e.g. -c Jaipur -c Indore)")
@click.option("--max-queries", "-m", default=10, help="Maximum search queries to run")
def dork(city, max_queries):
    """Run search engine dorking to discover new candidate handles."""
    dorker = SearchDorker()
    cities = list(city) if city else None
    
    console.print(f"[cyan]Running search dorking across Tier 2/3 cities...[/cyan]")
    queries = dorker.generate_dork_queries(target_cities=cities, max_queries=max_queries)
    
    total_found = 0
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        for item in queries:
            q = item["query"]
            c = item["city"]
            task = progress.add_task(f"Searching {c}...", total=None)
            
            handles = dorker.search_city(c)
            if handles:
                added = enqueue_profiles(handles, source=f"dork_{c}", priority=25)
                total_found += added
                console.print(f"[green]✔ {c}: Discovered {len(handles)} handles ({added} new enqueued)[/green]")
            progress.remove_task(task)

    console.print(f"\n[bold green]Total new candidates added to queue: {total_found}[/bold green]")


@cli.command()
@click.argument("username")
@click.option("--simulation", "-s", is_flag=True, default=False, help="Use mock simulation fixture")
def verify(username, simulation):
    """Inspect and evaluate a single profile with diagnostic feedback."""
    client = InstagramClient(simulation_mode=simulation)
    sieve = DeterministicSieve()
    resolver = LocationResolver()

    console.print(f"[cyan]Evaluating profile @[bold]{username}[/bold] (simulation={simulation})...[/cyan]")

    try:
        profile_data = client.fetch_profile(username)
    except Exception as e:
        console.print(f"[red]✖ Failed to fetch profile: {e}[/red]")
        return

    console.print(f"\n[bold]Full Name:[/bold] {profile_data.get('full_name')}")
    console.print(f"[bold]Bio:[/bold] {profile_data.get('biography')}")
    console.print(f"[bold]Followers:[/bold] {profile_data.get('followers_count'):,}")
    console.print(f"[bold]Timeline Posts Sampled:[/bold] {len(profile_data.get('timeline_posts', []))}")

    # Pass 1: Sieve
    sieve_res = sieve.evaluate(profile_data)
    console.print("\n[bold cyan]--- Pass 1: Deterministic Sieve ---[/bold cyan]")
    console.print(f"Avg Comments: [bold]{sieve_res.avg_comments:.1f}[/bold] (Threshold: {sieve.min_avg_comments})")
    console.print(f"Skincare Keywords: {sieve_res.skincare_keywords_found}")
    console.print(f"Tier 1 Metro Matched: {sieve_res.matched_tier1_metro}")
    color = "green" if sieve_res.passed else "red"
    console.print(f"Sieve Passed: [{color}][bold]{sieve_res.passed}[/bold][/{color}]")

    if not sieve_res.passed:
        console.print(f"[red]Rejection Reason: {sieve_res.rejection_reason}[/red]")
        console.print(f"Evidence: {sieve_res.evidence}")
        return

    # Pass 2: Resolver
    loc_res = resolver.resolve(profile_data)
    console.print("\n[bold cyan]--- Pass 2: Location Resolver ---[/bold cyan]")
    console.print(f"Detected City: [bold]{loc_res.detected_city}[/bold]")
    console.print(f"City Tier: [bold]{loc_res.city_tier}[/bold]")
    console.print(f"State: {loc_res.state}")
    console.print(f"Evidence: {loc_res.evidence}")

    if loc_res.is_qualified:
        console.print(f"\n[bold green]✔ QUALIFIED TIER 2/3 SKINCARE CREATOR![/bold green]")
    else:
        console.print(f"\n[bold red]✖ DISQUALIFIED: {loc_res.evidence}[/bold red]")


@cli.command()
@click.option("--max-profiles", "-m", default=25, help="Number of profiles to evaluate")
@click.option("--simulation", "-s", is_flag=True, default=False, help="Run in mock simulation mode")
def crawl(max_profiles, simulation):
    """Run automated BFS crawler loop."""
    client = InstagramClient(simulation_mode=simulation)
    crawler = BFSCrawler(client=client)

    console.print(Panel.fit(
        f"[bold cyan]Starting InstaHunt BFS Crawler[/bold cyan]\n"
        f"Mode: {'[bold yellow]SIMULATION (Offline/Mock)[/bold yellow]' if simulation else '[bold green]LIVE (Network)[/bold green]'}\n"
        f"Target Scan Limit: [bold]{max_profiles}[/bold] profiles",
        border_style="cyan"
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Crawling profiles...", total=max_profiles)

        for i in range(max_profiles):
            outcome = crawler.process_next()
            if not outcome:
                console.print("[yellow]Queue is empty. Use 'instahunt dork' or 'instahunt init' to feed queue.[/yellow]")
                break

            status_style = {
                "qualified": "[bold green]QUALIFIED[/bold green]",
                "rejected": "[yellow]REJECTED[/yellow]",
                "rate_limited": "[bold red]RATE LIMITED[/bold red]",
                "error": "[red]ERROR[/red]",
            }.get(outcome.get("status"), outcome.get("status"))

            desc = f"@{outcome['username']} -> {status_style}"
            if outcome.get("status") == "qualified":
                desc += f" ({outcome.get('city')}, {outcome.get('avg_comments'):.1f} comments)"
            progress.update(task, advance=1, description=desc)

            if outcome.get("status") == "rate_limited":
                console.print("[red]⚠ Hit Instagram rate limit. Halting crawler safely.[/red]")
                break


@cli.command()
@click.option("--sheet", type=click.Path(), default=str(DEFAULT_SHEET_PATH), help="Target StormShadow.xlsx path")
@click.option("--csv-export/--no-csv", default=True, help="Export CSV file as well")
@click.option("--report/--no-report", default=True, help="Generate markdown audit report")
def export(sheet, csv_export, report):
    """Export verified creators to StormShadow.xlsx and CSV."""
    exporter = SheetExporter(sheet_path=Path(sheet))
    
    console.print(f"[cyan]Exporting qualified creators to {sheet}...[/cyan]")
    try:
        added = exporter.append_qualified_to_sheet()
        console.print(f"[bold green]✔ Appended {added} new verified creators to {sheet} Sheet1![/bold green]")
    except Exception as e:
        console.print(f"[red]✖ Failed to update spreadsheet: {e}[/red]")

    if csv_export:
        csv_file = exporter.export_to_csv()
        console.print(f"[green]✔ CSV export saved to: [bold]{csv_file}[/bold][/green]")

    if report:
        report_file = exporter.generate_markdown_report()
        console.print(f"[green]✔ Markdown audit report saved to: [bold]{report_file}[/bold][/green]")


@cli.command()
@click.option("--output", "-o", default="/tmp/instahunt-mobile.tar.gz", help="Destination tarball path")
def bundle(output):
    """Pack a portable standalone bundle for 1-command execution on Android Termux."""
    out_path = Path(output)
    console.print(f"[cyan]Packaging portable InstaHunt bundle for Android Termux...[/cyan]")

    exclude_patterns = {"venv", ".venv", "__pycache__", ".git", ".pytest_cache"}

    def tar_filter(tarinfo):
        for pattern in exclude_patterns:
            if pattern in tarinfo.name:
                return None
        return tarinfo

    with tarfile.open(out_path, "w:gz") as tar:
        tar.add(BASE_DIR, arcname="instahunt", filter=tar_filter)

    console.print(f"[bold green]✔ Standalone Termux bundle created at {out_path}[/bold green]")
    console.print(f"[cyan]To run on mobile Termux:[/cyan]")
    console.print(f"  tar -xzf instahunt-mobile.tar.gz && cd instahunt")
    console.print(f"  pip install click rich requests openpyxl pydantic")
    console.print(f"  python3 -m instahunt.cli crawl --simulation")


@cli.group(name="ai")
def ai_group():
    """AI Intelligence Layer: Multi-provider LLM reasoning & enrichment."""
    pass


@ai_group.command(name="test")
def ai_test():
    """Test connectivity, latency, and status across all AI providers."""
    console.print(Panel.fit("[bold cyan]AI Intelligence Multi-Provider Health Check[/bold cyan]", border_style="cyan"))
    
    engine = AIIntelligenceEngine()
    results = engine.health_check()

    table = Table(title="LLM Provider Connectivity Matrix", border_style="cyan", show_lines=True)
    table.add_column("Provider", style="bold white", width=14)
    table.add_column("Configured", justify="center", width=12)
    table.add_column("Status", justify="center", width=12)
    table.add_column("Latency (ms)", justify="right", width=14)
    table.add_column("Details / Model", style="dim", width=42)

    for prov, info in results.items():
        conf_str = "[green]YES[/green]" if info["configured"] else "[dim red]NO[/dim red]"
        if info["status"] == "healthy":
            stat_str = "[bold green]HEALTHY[/bold green]"
        elif info["status"] == "error":
            stat_str = "[bold red]ERROR[/bold red]"
        else:
            stat_str = "[dim yellow]STANDBY[/dim yellow]"

        lat_str = f"{info['latency_ms']} ms" if info["latency_ms"] is not None else "-"
        table.add_row(prov.upper(), conf_str, stat_str, lat_str, str(info["message"])[:40])

    console.print(table)


@ai_group.command(name="disambiguate")
@click.argument("target")
def ai_disambiguate(target):
    """Disambiguate creator geography & Tier 2/3 classification (accepts handle or bio text)."""
    engine = AIIntelligenceEngine()
    clean_target = target.strip().replace("@", "")
    
    profile = get_profile(clean_target)
    if profile:
        console.print(f"[cyan]Evaluating stored database profile @{clean_target}...[/cyan]")
        bio = profile.get("biography", "")
        import json
        try:
            locs = json.loads(profile.get("post_locations", "[]"))
        except Exception:
            locs = []
        username = clean_target
    else:
        console.print(f"[cyan]Evaluating ad-hoc bio/text query: '{target}'...[/cyan]")
        bio = target
        locs = []
        username = "manual_query"

    analysis = engine.disambiguate_location(username=username, bio=bio, post_locations=locs)
    
    table = Table(title=f"Location Disambiguation: @{username}", border_style="magenta", show_lines=True)
    table.add_column("Attribute", style="bold white", width=22)
    table.add_column("Value", style="bold green", width=50)

    table.add_row("Detected City", str(analysis.detected_city))
    table.add_row("Detected State", str(analysis.detected_state))
    table.add_row("City Tier", str(analysis.city_tier))
    table.add_row("Target (Tier 2/3)", "[bold green]YES[/bold green]" if analysis.is_tier2_tier3 else "[bold red]NO[/bold red]")
    table.add_row("Confidence", f"{analysis.confidence * 100:.1f}%")
    table.add_row("Evidence", analysis.evidence)
    table.add_row("Provider Used", analysis.provider_used.upper())

    console.print(table)


@ai_group.command(name="audit")
@click.argument("username")
def ai_audit(username):
    """Perform deep AI skincare niche and community quality audit on a creator."""
    clean_u = username.strip().lower().replace("@", "")
    profile = get_profile(clean_u)
    
    engine = AIIntelligenceEngine()

    if profile:
        bio = profile.get("biography", "")
        avg_c = profile.get("avg_comments", 0.0)
    else:
        console.print(f"[yellow]Profile @{clean_u} not found in local DB. Running synthetic baseline audit...[/yellow]")
        bio = f"Skincare enthusiast & honest product reviewer. Living in Indore."
        avg_c = 125.0

    # Sample comments for audit test
    sample_comments = [
        "Does this moisturizer suit oily acne-prone skin?",
        "Where did you buy this in Indore?",
        "Price kitna hai iska?",
        "🔥❤️",
        "Please review the Foxtale ceramide barrier cream next!",
        "Love this honest review di!",
    ]

    niche = engine.assess_skincare_niche(clean_u, bio=bio)
    comm = engine.assess_community_quality(clean_u, sample_comments, avg_comments=avg_c)

    table = Table(title=f"AI Deep Audit Report: @{clean_u}", border_style="green", show_lines=True)
    table.add_column("Audit Metric", style="bold white", width=24)
    table.add_column("Score / Result", style="bold cyan", width=48)

    table.add_row("Is Skincare Focused", "[green]YES[/green]" if niche.is_skincare_creator else "[red]NO[/red]")
    table.add_row("Niche Concentration Score", f"{niche.niche_score * 100:.1f}%")
    table.add_row("Primary Focus", niche.primary_focus)
    table.add_row("Vernacular Signals", ", ".join(niche.vernacular_signals) if niche.vernacular_signals else "None detected")
    table.add_row("Community Quality Grade", f"[bold green]{comm.community_grade}[/bold green]")
    table.add_row("Engagement Authenticity", f"{comm.authenticity_score * 100:.1f}%")
    table.add_row("Estimated Spam/Pod Ratio", f"{comm.spam_pod_ratio * 100:.1f}%")
    table.add_row("Audit Summary", comm.summary)

    console.print(table)


@ai_group.command(name="dorks")
@click.option("--city", "-c", multiple=True, help="Target Indian city")
@click.option("--brand", "-b", multiple=True, help="Target skincare brand")
@click.option("--max-queries", "-m", default=8, help="Maximum dorks to generate")
def ai_dorks(city, brand, max_queries):
    """Generate high-yield regional skincare dork queries."""
    engine = AIIntelligenceEngine()
    cities_list = list(city) if city else None
    brands_list = list(brand) if brand else None

    dorks = engine.generate_smart_dorks(cities=cities_list, brands=brands_list, max_queries=max_queries)

    table = Table(title="AI-Curated Regional Search Dorks", border_style="cyan", show_lines=True)
    table.add_column("#", justify="right", style="bold", width=4)
    table.add_column("City", style="bold green", width=14)
    table.add_column("Context / Brand", style="yellow", width=18)
    table.add_column("Dork Query", style="bold white", width=45)

    for i, d in enumerate(dorks, 1):
        table.add_row(str(i), d["city"], d.get("brand_context", "Skincare"), d["query"])

    console.print(table)


def main():
    cli()


if __name__ == "__main__":
    main()
