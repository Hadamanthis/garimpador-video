import time
import requests
from datetime import datetime, timezone, timedelta

VIDEO_DOMAINS = {"v.redd.it", "youtube.com", "youtu.be", "streamable.com", "gfycat.com"}
HEADERS = {"User-Agent": "garimpador/1.0 (leitura pública)"}


def _is_video(post: dict) -> bool:
    if post.get("is_video"):
        return True
    domain = post.get("domain", "") or ""
    return any(vd in domain for vd in VIDEO_DOMAINS)


def _duration(post: dict) -> int | None:
    try:
        return post["media"]["reddit_video"]["duration"]
    except (TypeError, KeyError):
        return None


def _fetch_hot(subreddit: str, limit: int = 50) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return [child["data"] for child in resp.json()["data"]["children"]]


def scrape(config: dict) -> list[dict]:
    cfg = config["sources"]["reddit"]
    if not cfg.get("enabled", False):
        return []

    max_age = timedelta(days=config["filters"]["max_age_days"])
    min_score = config["filters"]["min_score_reddit"]
    min_dur = config["filters"]["min_duration_seconds"]
    max_dur = config["filters"]["max_duration_seconds"]
    cutoff = datetime.now(timezone.utc) - max_age

    results = []
    for sub_name in cfg["subreddits"]:
        try:
            posts = _fetch_hot(sub_name)
            for post in posts:
                created = datetime.fromtimestamp(post["created_utc"], tz=timezone.utc)
                if created < cutoff:
                    continue
                if post.get("score", 0) < min_score:
                    continue
                if not _is_video(post):
                    continue

                duration = _duration(post)
                if duration is not None and (duration < min_dur or duration > max_dur):
                    continue

                results.append({
                    "url": post["url"],
                    "title": post["title"],
                    "source": f"reddit/{sub_name}",
                    "duration": duration,
                    "score": post.get("score", 0),
                    "description": (post.get("selftext") or "")[:500],
                    "age_hours": round(
                        (datetime.now(timezone.utc) - created).total_seconds() / 3600, 1
                    ),
                })
            time.sleep(1)  # respeita rate limit da API pública
        except Exception as e:
            print(f"[reddit] erro em r/{sub_name}: {e}")

    return results
