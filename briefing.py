import os
import anthropic

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
print(script)