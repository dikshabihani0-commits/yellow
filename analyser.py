import json
import os
from groq import Groq, NotFoundError, APIStatusError
from dotenv import load_dotenv

load_dotenv()

# Tried in order; falls through when Groq returns 404 model_not_found.
MODELS = [
    os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
]

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set. Add it to your .env file.")
        _client = Groq(api_key=api_key)
    return _client


def analyse_posts(posts: list[dict], subreddit: str) -> dict:
    if not posts:
        raise ValueError("No posts to analyse.")

    # Groq's free tier caps requests at ~8000 tokens/minute (input + output),
    # so keep the prompt small and halve it again if Groq still says 413.
    n_posts = 60
    while True:
        try:
            return _analyse(posts[:n_posts], len(posts), subreddit)
        except APIStatusError as e:
            if e.status_code != 413 or n_posts <= 15:
                raise
            n_posts //= 2


def _analyse(posts: list[dict], total: int, subreddit: str) -> dict:
    post_snippets = []
    for i, p in enumerate(posts, 1):
        body_preview = (p["body"] or "")[:120].replace("\n", " ").strip()
        post_snippets.append(f"{i}. [{p['date']}] {p['title']}\n   {body_preview}")

    posts_text = "\n\n".join(post_snippets)

    prompt = f"""You are a content strategist for Yellow, a women's health brand focused on menopause support.
You have just read {total} recent posts from the Reddit community r/{subreddit}.

Here are the posts (title + excerpt):

{posts_text}

---

Analyse these posts and return a JSON object with EXACTLY these keys:

{{
  "trending_topics": [
    {{"topic": "...", "description": "...", "post_count": N, "example": "...", "post_index": N}}
  ],
  "sentiment": {{
    "positive_pct": N,
    "neutral_pct": N,
    "negative_pct": N,
    "summary": "..."
  }},
  "pain_points": ["...", "...", "..."],
  "questions_asked": ["...", "...", "..."],
  "content_ideas": [
    {{"title": "...", "format": "...", "rationale": "..."}}
  ]
}}

Rules:
- trending_topics: top 5 themes by frequency, each with a count estimate, a real example title from the posts, and post_index (the 1-based number of that post from the list above)
- sentiment: percentages must sum to 100; summary is 1-2 sentences
- pain_points: top 5 specific frustrations or struggles mentioned
- questions_asked: top 5 questions the community is asking
- content_ideas: 6-8 ideas tailored for Yellow's menopause health brand; format can be "Blog post", "Instagram carousel", "Newsletter", "Short video", "Guide", "Email series", etc.
- Return ONLY valid JSON with no markdown fences, no commentary."""

    client = _get_client()
    last_error = None
    for model in MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except NotFoundError as e:  # model retired or not available to this key
            last_error = e
    raise last_error
