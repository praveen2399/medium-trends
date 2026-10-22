import os
from email.utils import parsedate_to_datetime

import anthropic
import feedparser

# ---------- Step 1: collect and rank posts ----------
TAGS = [
    "artificial-intelligence", "software-architecture", "fintech",
    "llm", "banking", "ai-agents",
]
FINANCE_WORDS = ["bank", "fintech", "payment", "finance"]

posts = {}
for tag in TAGS:
    feed = feedparser.parse(f"https://medium.com/feed/tag/{tag}")
    for entry in feed.entries:
        link = entry.link.split("?")[0]
        if link in posts:
            posts[link]["tag_hits"] += 1
            continue
        text = (entry.title + " " + entry.get("summary", "")).lower()
        try:
            published = parsedate_to_datetime(entry.published).timestamp()
        except Exception:
            published = 0
        posts[link] = {
            "title": entry.title,
            "link": link,
            "published": published,
            "snippet": entry.get("summary", "")[:500],
            "tag_hits": 1,
            "agents_in_finance": "agent" in text
                and any(w in text for w in FINANCE_WORDS),
        }

print(f"Collected {len(posts)} posts")
if not posts:
    raise SystemExit("No posts found - Medium feeds may be blocking requests.")

top5 = sorted(
    posts.values(),
    key=lambda p: (p["agents_in_finance"], p["tag_hits"], p["published"]),
    reverse=True,
)[:5]

for i, p in enumerate(top5, 1):
    print(f"{i}. {p['title']}\n   {p['link']}")

# ---------- Step 2: write the spoken briefing ----------
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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
    model="claude-haiku-4-5",
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
