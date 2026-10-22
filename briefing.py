import json
import os
import re
from email.utils import parsedate_to_datetime

import anthropic
import feedparser

MODEL = "claude-haiku-4-5"

# ---------- Sources ----------
# Tag feeds: the latest posts on each topic.
TAGS = [
    "artificial-intelligence", "software-architecture", "fintech",
    "llm", "banking", "ai-agents",
]

# Curated publications: editors pick these posts, so quality is pre-filtered.
# Add or remove slugs freely; a feed that returns nothing is just skipped.
PUBLICATIONS = [
    "towards-artificial-intelligence",  # Towards AI
    "ai-advances",                      # AI Advances
    "gitconnected",                     # Level Up Coding
    "data-science-collective",          # Data Science Collective
]

FINANCE_WORDS = ["bank", "fintech", "payment", "finance", "lending", "credit card"]
MAX_CANDIDATES = 60


def clean(text):
    """Strip HTML tags from feed snippets."""
    return re.sub(r"<[^>]+>", " ", text or "").replace("&nbsp;", " ").strip()


# ---------- Step 1: collect posts ----------
feeds = [(f"tag:{t}", f"https://medium.com/feed/tag/{t}") for t in TAGS]
feeds += [(f"pub:{p}", f"https://medium.com/feed/{p}") for p in PUBLICATIONS]

posts = {}
for source, url in feeds:
    feed = feedparser.parse(url)
    print(f"{source}: {len(feed.entries)} posts")
    for entry in feed.entries:
        link = entry.link.split("?")[0]
        if link in posts:
            posts[link]["hits"] += 1
            posts[link]["sources"].add(source)
            continue
        snippet = clean(entry.get("summary", ""))[:400]
        text = (entry.title + " " + snippet).lower()
        try:
            published = parsedate_to_datetime(entry.published).timestamp()
        except Exception:
            published = 0
        posts[link] = {
            "title": entry.title,
            "link": link,
            "published": published,
            "snippet": snippet,
            "hits": 1,
            "sources": {source},
            "agents_in_finance": "agent" in text
                and any(w in text for w in FINANCE_WORDS),
        }

print(f"Collected {len(posts)} unique posts")
if not posts:
    raise SystemExit("No posts found - Medium feeds may be blocking requests.")


def rule_score(p):
    curated = any(s.startswith("pub:") for s in p["sources"])
    return (p["agents_in_finance"], curated, p["hits"], p["published"])


# Shortlist by the simple rules, then let the LLM pick the final five.
candidates = sorted(posts.values(), key=rule_score, reverse=True)[:MAX_CANDIDATES]

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ---------- Step 2: LLM picks the five most significant ----------
listing = "\n".join(
    f"[{i}] {p['title']} (sources: {', '.join(sorted(p['sources']))})\n    {p['snippet'][:250]}"
    for i, p in enumerate(candidates)
)

pick_prompt = f"""You are curating a daily trends briefing for a senior engineering
leader at a large bank. Interests: AI and LLMs, AI agents (especially in banking and
fintech), software architecture, and the financial industry.

From the Medium posts below, choose the 5 that best signal an important trend or
offer real substance. Prefer posts from curated publications, posts appearing under
several sources, and concrete technical or industry insight. Avoid clickbait,
listicles, beginner tutorials and near-duplicate topics.

Reply with only a JSON array of the 5 index numbers, most important first, e.g. [3, 0, 12, 7, 21].

{listing}"""

top5 = None
try:
    reply = client.messages.create(
        model=MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": pick_prompt}],
    ).content[0].text
    indices = json.loads(re.search(r"\[[\d,\s]+\]", reply).group())
    chosen = [candidates[i] for i in dict.fromkeys(indices) if 0 <= i < len(candidates)]
    if len(chosen) >= 3:
        top5 = chosen[:5]
        print("LLM picked:", indices)
except Exception as e:
    print("LLM pick failed, falling back to rules:", e)

if not top5:
    top5 = candidates[:5]

for i, p in enumerate(top5, 1):
    print(f"{i}. {p['title']}\n   {p['link']}")

# ---------- Step 3: write the spoken briefing ----------
articles = "\n\n".join(
    f"{i}. {p['title']}\nSnippet: {p['snippet']}\nAgents in finance: {p['agents_in_finance']}"
    for i, p in enumerate(top5, 1)
)

prompt = f"""You are a friendly tech news anchor. Write a spoken daily briefing,
about 3 minutes long, covering these five Medium posts on AI, architecture and fintech.
Open with a one-line greeting, then cover each story in two or three sentences,
saying why it matters for a senior engineering leader in banking.
Lead with any AI-agents-in-finance stories. End with the overall trend you notice
and recommend which one or two posts are worth reading in full.
Plain spoken text only: no bullet points, no markdown, no URLs.

{articles}"""

response = client.messages.create(
    model=MODEL,
    max_tokens=1200,
    messages=[{"role": "user", "content": prompt}],
)

script = response.content[0].text
with open("briefing.txt", "w") as f:
    f.write(script)

with open("links.txt", "w") as f:
    for i, p in enumerate(top5, 1):
        f.write(f"{i}. {p['title']}\n{p['link']}\n\n")

print("\n--- BRIEFING ---\n")
print(script)
