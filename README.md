# InstaHunt 🎯

> **Automated Instagram Skincare Creator Discovery Engine**  
> Tailored for identifying verified skincare creators from **Indian Tier 2 & Tier 3 cities** with **100+ average comments** per post.

---

## 1. Overview & Unit Economics

At client payouts of **$1–$2 per 100 verified creators** ($0.01–$0.02 per qualified lead), scraping via paid third-party proxies (Apify, BrightData) or calling LLMs on every raw profile results in immediate financial loss.

**InstaHunt solves this with a 4-Stage Zero-Cost Funnel:**
```
[ Raw Discovery Queue ]
       │
       ▼
[ Pass 1: Zero-Cost Deterministic Python Sieve ]
  ├─ Mathematical Comment Filter: avg_comments >= 100 on last 12 posts (excluding pinned giveaways)
  ├─ Hard Tier 1 Metro Blacklist: Instant regex drop (Mumbai, Delhi/NCR, Bengaluru, Hyderabad, Chennai, Kolkata, Pune, Ahmedabad)
  └─ Skincare Keyword Scoring: Bio + caption density check
       │ (Filters ~90% of profiles in milliseconds for $0.00)
       ▼
[ Pass 2: Location & Niche Resolver ]
  ├─ Tier 2 & Tier 3 Knowledge Base: 180+ Indian cities & aliases (Jaipur, Indore, Lucknow, Kochi, Coimbatore, etc.)
  ├─ Multi-Layer Matching: Bio text ➔ Post geo-tags ➔ Captions/Hashtags
  └─ Optional Free-Tier LLM: Groq / OpenRouter / Gemini Flash for ambiguous edge cases
       │
       ▼
[ Stage 3: Graph Chaining & Queue Expansion ]
  └─ Qualified creators' suggested profiles (`edge_chaining`) are boosted to Priority 100 in the BFS queue
       │
       ▼
[ Stage 4: Deduplication & Sheet Export ]
  ├─ Deduplicated against existing client links in StormShadow.xlsx Sheet1
  └─ Formatted with client tracking token: `https://www.instagram.com/{username}?stkn={token}`
```

---

## 2. Project Structure

```
/tmp/workspace/instahunt/
├── instahunt/
│   ├── __init__.py
│   ├── cli.py         # Rich interactive CLI commands
│   ├── client.py      # Instagram web API client & session manager
│   ├── config.py      # Geographical knowledge base & parameters
│   ├── crawler.py     # BFS crawl loop & priority queue orchestrator
│   ├── db.py          # SQLite persistence (profiles, queue, stats)
│   ├── dorker.py      # Search engine dorking (Bing, DuckDuckGo Lite)
│   ├── exporter.py    # StormShadow.xlsx, CSV, and markdown export
│   ├── llm.py         # Free-tier Groq/OpenRouter fallback classifier
│   ├── resolver.py    # Pass 2 Tier 2/3 location resolution
│   └── sieve.py       # Pass 1 deterministic mathematical sieve
├── data/
│   ├── StormShadow.xlsx  # Client deliverables spreadsheet
│   └── instahunt.db      # Local SQLite database
├── exports/
│   ├── qualified_creators.csv
│   └── instahunt_audit_report.md
├── tests/             # 15 automated unit tests
├── requirements.txt
├── setup.py
└── README.md
```

---

## 3. CLI Command Reference

The CLI is available as `instahunt` (symlinked into `~/.local/bin/instahunt`):

```bash
# Initialize DB and import baseline records from StormShadow.xlsx
instahunt init

# View the real-time funnel dashboard and rejection breakdown
instahunt status

# Inspect and evaluate a single profile with diagnostic output
instahunt verify sonali.rao22 --simulation
instahunt verify mumbai_skincare_star --simulation
instahunt verify <username>

# Run search engine dorking to discover fresh handles for Tier 2/3 cities
instahunt dork -c Jaipur -c Indore -c Lucknow

# Run the automated BFS crawler loop
instahunt crawl --simulation -m 25
instahunt crawl -m 50  # Live network mode

# Export newly qualified creators to StormShadow.xlsx, CSV, and audit report
instahunt export

# Manage Instagram session cookies
instahunt session set <your_sessionid_cookie>
instahunt session show
instahunt session test

# Pack a portable standalone bundle for Android Termux
instahunt bundle
```

---

## 4. Running on Android Termux (Residential Mobile IP)

Because Instagram actively throttles datacenter IPs (GCP Cloud Shell) with HTTP 429 when unauthenticated, running the discovery engine directly on your **mobile phone via Termux** (over cellular 4G/5G or home WiFi) provides a natural residential IP that bypasses datacenter blocks.

### 1-Command Setup on Termux:
```bash
# 1. Download the pre-packaged bundle from Google Drive
rclone copy "depot13:Data/Reddit clients/InstaHunt/instahunt-mobile.tar.gz" .

# 2. Extract and enter
tar -xzf instahunt-mobile.tar.gz && cd instahunt

# 3. Install lightweight dependencies
pip install click rich requests openpyxl pydantic

# 4. Initialize and run!
python3 -m instahunt.cli init
python3 -m instahunt.cli crawl -m 50
```

---

## 5. Optional Service Account Enhancement (`enricher` & `audit`)

You can optionally link a secondary/burner Instagram account stored in your Infisical vault (`Insta_svc_acc_username` and `Insta_svc_acc_pwd`) for advanced confidence scoring without creating any dependency in the main discovery pipeline:

* **100% Decoupled**: If credentials or session are absent or challenged, the core engine continues unaffected.
* **Engagement Authenticity Audit**: Analyzes sample comments on qualified creators to verify whether high comment counts reflect genuine community discussions (e.g. skin type questions, product inquiries, regional language remarks) versus generic emoji spam or giveaway pods.
* **Deep Chaining Expansion**: When an active session is available, queries extended similar creators (`get_similar()`) to expand the discovery frontier.

```bash
# Check service account connection status
infisical run --env=dev -- instahunt session svc-status

# Non-blocking login check / session token refresh
infisical run --env=dev -- instahunt session svc-login

# Audit community engagement authenticity & assign quality grade (Grade A/B/C)
instahunt audit <username>
```

---

## 6. Safety & Anti-Ban Architecture

1. **Human Pacing & Jitter**: Randomized delay (`12.0` to `25.0` seconds) between profile requests.
2. **Batch Cooldowns**: Pauses for 5 minutes after every 50 requests to keep request velocity natural.
3. **Passive Graph Extraction**: Extracts bio, recent posts, and suggested profiles from a single XHR payload without clicking multiple post DOMs.
4. **Rate Limit Detection**: Automatically detects HTTP 429 responses and gracefully halts without losing queue progress.
