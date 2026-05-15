import os
import isodate
from datetime import datetime, timezone, timedelta
from googleapiclient.discovery import build


def _parse_duration(iso: str) -> int:
    try:
        return int(isodate.parse_duration(iso).total_seconds())
    except Exception:
        return 0


def scrape(config: dict) -> list[dict]:
    cfg = config["sources"]["youtube"]
    if not cfg.get("enabled", False):
        return []

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("[youtube] YOUTUBE_API_KEY não configurada, pulando.")
        return []

    youtube = build("youtube", "v3", developerKey=api_key)

    max_age = timedelta(days=config["filters"]["max_age_days"])
    min_dur = config["filters"]["min_duration_seconds"]
    max_dur = config["filters"]["max_duration_seconds"]
    published_after = (datetime.now(timezone.utc) - max_age).strftime("%Y-%m-%dT%H:%M:%SZ")

    results = []
    for topic in config.get("topics", []):
        try:
            search_resp = youtube.search().list(
                part="id,snippet",
                q=topic,
                type="video",
                videoDuration="short",       # < 4 min (YouTube categoriza assim)
                publishedAfter=published_after,
                order="relevance",
                maxResults=cfg.get("max_results", 10),
                relevanceLanguage="pt",
            ).execute()

            video_ids = [item["id"]["videoId"] for item in search_resp.get("items", [])]
            if not video_ids:
                continue

            details_resp = youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(video_ids),
            ).execute()

            for item in details_resp.get("items", []):
                duration = _parse_duration(item["contentDetails"]["duration"])
                if duration < min_dur or duration > max_dur:
                    continue

                snippet = item["snippet"]
                stats = item.get("statistics", {})
                published = datetime.fromisoformat(
                    snippet["publishedAt"].replace("Z", "+00:00")
                )
                age_hours = round(
                    (datetime.now(timezone.utc) - published).total_seconds() / 3600, 1
                )

                results.append({
                    "url": f"https://youtu.be/{item['id']}",
                    "title": snippet["title"],
                    "source": "youtube",
                    "duration": duration,
                    "score": int(stats.get("viewCount", 0)),
                    "description": snippet.get("description", "")[:500],
                    "age_hours": age_hours,
                    "channel": snippet.get("channelTitle", ""),
                })
        except Exception as e:
            print(f"[youtube] erro no tópico '{topic}': {e}")

    seen_urls: set[str] = set()
    deduped = []
    for v in results:
        if v["url"] not in seen_urls:
            seen_urls.add(v["url"])
            deduped.append(v)

    return deduped
