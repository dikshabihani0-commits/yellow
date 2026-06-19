import requests
import time
from datetime import datetime, timezone

BASE_URL = "https://arctic-shift.photon-reddit.com/api/posts/search"


def fetch_posts(subreddit: str, days: int = 7) -> list[dict]:
    cutoff = int(time.time() - days * 86400)
    posts = []
    before = None  # paginate backwards by passing oldest post's timestamp

    for _ in range(5):  # max 5 pages = 500 posts
        params = {
            "subreddit": subreddit,
            "limit": 100,
            "after": cutoff,
            "sort": "desc",
        }
        if before:
            params["before"] = before

        resp = requests.get(BASE_URL, params=params, timeout=10)

        if resp.status_code == 404:
            raise ValueError(f"Subreddit r/{subreddit} not found.")
        if resp.status_code in (403, 401):
            raise ValueError(f"r/{subreddit} is private or restricted.")
        resp.raise_for_status()

        data = resp.json().get("data", [])
        if not data:
            break

        for p in data:
            posts.append({
                "title": p.get("title", ""),
                "body": p.get("selftext", ""),
                "score": p.get("score", 0),
                "comments": p.get("num_comments", 0),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "date": datetime.fromtimestamp(p["created_utc"], tz=timezone.utc).strftime("%Y-%m-%d"),
            })

        if len(data) < 100:
            break  # no more pages

        before = data[-1]["created_utc"]  # oldest post timestamp → next page

    return posts
