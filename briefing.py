import json
import os
import re
from email.utils import parsedate_to_datetime

import anthropic
import feedparser

MODEL = "claude-haiku-4-5"
PER_TAG = 5

# ---------- Categories ----------
# Each tag is a category. Keywords pull matching posts from the curated
# publications into that category too.
CATEGORIES = {
    "artificial-intelligence": {"name": "AI", "keywords": [r"\bai\b", "artificial intelligence", "machine learning", "deep learning"]},
    "llm": {"name": "LLMs", "keywords": [r"\bllms?\b", "language model", r"\brag\b", r"\bgpt", "claude", "gemini", "prompt"]},
    "ai-agents": {"name": "AI Agents", "keywords": [r"\bagents?\b", "agentic", r"\bmcp\b"]},
    "software-architecture": {"name": "Software Architecture", "keywords": ["architecture", "microservice", "system design", "distributed system", "event-driven"]},
    "fintech": {"name": "Fintech", "keywords": ["fintech", "payment", "lending", "crypto", "stablecoin"]},
    "banking": {"name": "Banking", "keywords": [r"\bbank", "credit card", "core banking"]},
}

# Curated publications: editors pick these posts, so quality is pre-filtered.
# A feed that returns nothing is just skipped.
PUBLICATIONS = [
    "towards-artificial-intelligence",  # Towards AI
    "ai-advances",                      # AI Advances
    "gitconnected",                     # Level Up Coding
    "data-science-collective",          # Data Science Collective
]


def clean(text):
    """Strip HTML tags from feed snippets."""
    return re.sub(r"<[^>]+>", " ", text or "").replace("&nbsp;", " ").strip()


def read_feed(url, source):
    feed = feedparser.parse(url)
    print(f"{source}: {len(feed.entries)} posts")
    items = []
    for entry in feed.entries:
        try:
            published = parsedate_to_datetime(entry.published).timestamp()
        except Exception:
            published = 0
        items.append({
            "title": entry.title,
            "link": entry.link.split("?")[0],
            "published": published,
            "snippet": clean(entry.get("summary", ""))[:400],
            "curated": source.startswith("pub:"),
        })
    return items


# ---------- Step 1: collect posts per category ----------
pub_posts = []
for p in PUBLICATIONS:
    pub_posts += read_feed(f"https://medium.com/feed/{p}", f"pub:{p}")

pools = {}
for tag, cat in CATEGORIES.items():
    pool = {post["link"]: post for post in read_feed(f"https://medium.com/feed/tag/{tag}", f"tag:{tag}")}
    for post in pub_posts:
        text = (post["title"] + " " + post["snippet"]).lower()
        if any(re.search(k, text) for k in cat["keywords"]):
            pool.setdefault(post["link"], post)
    pools[tag] = sorted(pool.values(), key=lambda x: (x["curated"], x["published"]), reverse=True)[:20]

if not any(pools.values()):
    raise SystemExit("No posts found - Medium feeds may be blocking requests.")

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ---------- Step 2: LLM picks the top 5 in each category ----------
listing = ""
for tag, pool in pools.items():
    listing += f"\n## {tag}\n"
    for i, post in enumerate(pool):
        mark = " (curated)" if post["curated"] else ""
        listing += f"[{i}] {post['title']}{mark}\n    {post['snippet'][:200]}\n"

pick_prompt = f"""You are curating a daily trends briefing for a senior engineering
leader at a large bank.

For EACH category below, choose the {PER_TAG} posts that best signal an important trend
or offer real substance. Prefer curated posts and concrete technical or industry
insight. Avoid clickbait, listicles and beginner tutorials. Never pick the same
article (same title) in more than one category.

Reply with only a JSON object mapping each category to a list of index numbers,
most important first, e.g. {{"llm": [3, 0, 7, 1, 9], ...}}.
{listing}"""

picks = {}
try:
    reply = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": pick_prompt}],
    ).content[0].text
    picks = json.loads(re.search(r"\{.*\}", reply, re.S).group())
except Exception as e:
    print("LLM pick failed, falling back to newest posts:", e)

top = {}
used = set()
for tag, pool in pools.items():
    indices = [i for i in picks.get(tag, []) if isinstance(i, int) and 0 <= i < len(pool)]
    indices += [i for i in range(len(pool)) if i not in indices]  # fill any gaps
    chosen = []
    for i in indices:
        post = pool[i]
        if post["link"] not in used:
            chosen.append(post)
            used.add(post["link"])
        if len(chosen) == PER_TAG:
            break
    top[tag] = chosen

for tag, posts in top.items():
    print(f"\n== {CATEGORIES[tag]['name']} ==")
    for i, p in enumerate(posts, 1):
        print(f"{i}. {p['title']}\n   {p['link']}")

# ---------- Step 3: write the spoken briefing ----------
articles = ""
for tag, posts in top.items():
    articles += f"\n### {CATEGORIES[tag]['name']}\n"
    for i, p in enumerate(posts, 1):
        articles += f"{i}. {p['title']}\nSnippet: {p['snippet']}\n"

prompt = f"""You are a friendly tech news anchor. Write a spoken daily briefing of
about 8 to 10 minutes, covering the Medium posts below, grouped by category.
Open with a one-line greeting. Introduce each category with a short spoken
transition, then cover each story in one or two sentences, saying why it matters for
a senior engineering leader in banking. Close each category with a one-line takeaway.
End with the big trend across all categories and recommend two or three posts worth
reading in full.
Plain spoken text only: no headings, no bullet points, no markdown, no URLs.
{articles}"""

response = client.messages.create(
    model=MODEL,
    max_tokens=3000,
    messages=[{"role": "user", "content": prompt}],
)

script = response.content[0].text
with open("briefing.txt", "w") as f:
    f.write(script)

with open("links.txt", "w") as f:
    for tag, posts in top.items():
        f.write(f"## {CATEGORIES[tag]['name']}\n\n")
        for i, p in enumerate(posts, 1):
            f.write(f"{i}. {p['title']}\n{p['link']}\n\n")

print("\n--- BRIEFING ---\n")
print(script)
