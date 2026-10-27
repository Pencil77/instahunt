"""
BFS Crawler and Orchestration Engine for InstaHunt.
Pulls from priority queue, fetches profile payloads, runs the 2-stage sieve,
boosts suggested accounts of qualified creators, and records results.
"""

import time
from typing import Callable, Dict, Optional

from instahunt.client import InstagramClient, RateLimitException
from instahunt.db import (
    boost_related_priority,
    enqueue_profiles,
    get_next_queued_profile,
    mark_queue_status,
    upsert_profile,
)
from instahunt.resolver import LocationResolver
from instahunt.sieve import DeterministicSieve


class BFSCrawler:
    def __init__(
        self,
        client: InstagramClient,
        sieve: Optional[DeterministicSieve] = None,
        resolver: Optional[LocationResolver] = None,
        on_progress: Optional[Callable[[Dict], None]] = None,
    ):
        self.client = client
        self.sieve = sieve or DeterministicSieve()
        self.resolver = resolver or LocationResolver()
        self.on_progress = on_progress

    def process_next(self) -> Optional[Dict]:
        """Fetch and evaluate the next profile in the queue."""
        item = get_next_queued_profile()
        if not item:
            return None

        queue_id, username, source = item
        outcome = {
            "queue_id": queue_id,
            "username": username,
            "source": source,
            "status": "error",
            "message": "",
        }

        try:
            # 1. Fetch Instagram Profile Data
            profile_data = self.client.fetch_profile(username)

            # 2. Stage 1: Deterministic Sieve (Math + Tier 1 Blacklist + Skincare)
            sieve_res = self.sieve.evaluate(profile_data)

            # Extract suggested profiles
            suggested = profile_data.get("suggested_profiles", [])

            if not sieve_res.passed:
                # Rejected at Stage 1
                profile_record = {
                    "username": username,
                    "full_name": profile_data.get("full_name", ""),
                    "biography": profile_data.get("biography", ""),
                    "followers_count": profile_data.get("followers_count", 0),
                    "posts_count": profile_data.get("posts_count", 0),
                    "avg_comments": sieve_res.avg_comments,
                    "post_locations": [p.get("location_name", "") for p in profile_data.get("timeline_posts", [])],
                    "detected_city": None,
                    "city_tier": "Tier 1" if sieve_res.has_tier1_match else "Unknown",
                    "is_skincare": sieve_res.is_skincare,
                    "status": "rejected",
                    "rejection_reason": sieve_res.rejection_reason,
                    "evidence": sieve_res.evidence,
                }
                upsert_profile(profile_record)
                mark_queue_status(queue_id, "completed")

                # If bio still had skincare keywords, enqueue suggested profiles at low priority
                if sieve_res.skincare_keywords_found and suggested:
                    enqueue_profiles(suggested, source=f"chaining_{username}", priority=20)

                outcome.update({
                    "status": "rejected",
                    "reason": sieve_res.rejection_reason,
                    "avg_comments": sieve_res.avg_comments,
                    "evidence": sieve_res.evidence,
                })
                if self.on_progress:
                    self.on_progress(outcome)
                return outcome

            # 3. Stage 2: Location & Niche Resolver
            loc_res = self.resolver.resolve(profile_data)

            if loc_res.is_qualified:
                # Fully Qualified Tier 2 / Tier 3 Skincare Creator!
                profile_record = {
                    "username": username,
                    "full_name": profile_data.get("full_name", ""),
                    "biography": profile_data.get("biography", ""),
                    "followers_count": profile_data.get("followers_count", 0),
                    "posts_count": profile_data.get("posts_count", 0),
                    "avg_comments": sieve_res.avg_comments,
                    "post_locations": [p.get("location_name", "") for p in profile_data.get("timeline_posts", [])],
                    "detected_city": loc_res.detected_city,
                    "city_tier": loc_res.city_tier,
                    "is_skincare": True,
                    "status": "qualified",
                    "rejection_reason": None,
                    "evidence": f"{sieve_res.evidence} | {loc_res.evidence}",
                }
                upsert_profile(profile_record)
                mark_queue_status(queue_id, "completed")

                # Graph Chaining Boost: Since this creator is verified, boost related profiles to front!
                if suggested:
                    boost_related_priority(suggested, boost_priority=100)

                outcome.update({
                    "status": "qualified",
                    "city": loc_res.detected_city,
                    "tier": loc_res.city_tier,
                    "avg_comments": sieve_res.avg_comments,
                    "evidence": loc_res.evidence,
                    "boosted_count": len(suggested),
                })
            else:
                # Rejected at Stage 2 (e.g. unknown or unverified location)
                profile_record = {
                    "username": username,
                    "full_name": profile_data.get("full_name", ""),
                    "biography": profile_data.get("biography", ""),
                    "followers_count": profile_data.get("followers_count", 0),
                    "posts_count": profile_data.get("posts_count", 0),
                    "avg_comments": sieve_res.avg_comments,
                    "post_locations": [p.get("location_name", "") for p in profile_data.get("timeline_posts", [])],
                    "detected_city": loc_res.detected_city,
                    "city_tier": loc_res.city_tier,
                    "is_skincare": True,
                    "status": "rejected",
                    "rejection_reason": f"unqualified_location_{loc_res.city_tier}",
                    "evidence": loc_res.evidence,
                }
                upsert_profile(profile_record)
                mark_queue_status(queue_id, "completed")

                outcome.update({
                    "status": "rejected",
                    "reason": f"location_{loc_res.city_tier}",
                    "avg_comments": sieve_res.avg_comments,
                    "evidence": loc_res.evidence,
                })

        except RateLimitException as rle:
            mark_queue_status(queue_id, "queued", last_error="HTTP 429 Rate Limited")
            outcome.update({
                "status": "rate_limited",
                "message": str(rle),
            })
        except Exception as e:
            mark_queue_status(queue_id, "failed", last_error=str(e)[:100])
            outcome.update({
                "status": "error",
                "message": str(e),
            })

        if self.on_progress:
            self.on_progress(outcome)
        return outcome

    def run_crawler_loop(self, max_profiles: int = 50, stop_on_ratelimit: bool = True):
        """Run continuous BFS crawler loop up to max_profiles."""
        processed = 0
        while processed < max_profiles:
            res = self.process_next()
            if not res:
                break
            if res.get("status") == "rate_limited" and stop_on_ratelimit:
                break
            processed += 1
        return processed
