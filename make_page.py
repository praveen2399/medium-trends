import datetime
import html
import os

os.makedirs("site", exist_ok=True)
today = datetime.date.today().strftime("%A, %B %d, %Y")
script = html.escape(open("briefing.txt").read())

links = ""
for block in open("links.txt").read().strip().split("\n\n"):
    lines = block.strip().split("\n")
    if len(lines) >= 2:
        title, url = lines[0], lines[1]
        links += f'    <li><a href="{html.escape(url)}">{html.escape(title)}</a></li>\n'

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Trends Briefing</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 680px; margin: 0 auto;
         padding: 16px; line-height: 1.6; background: #fafafa; color: #222; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #121212; color: #eee; }}
    a {{ color: #8ab4f8; }}
  }}
  audio {{ width: 100%; margin: 12px 0; }}
  .script {{ white-space: pre-wrap; }}
</style>
</head>
<body>
  <h1>Daily Trends Briefing</h1>
  <p>{today}</p>
  <audio controls src="briefing.mp3"></audio>
  <h2>Today's top 5</h2>
  <ol>
{links}  </ol>
  <h2>Script</h2>
  <div class="script">{script}</div>
</body>
</html>"""

with open("site/index.html", "w") as f:
    f.write(page)

print("Page written to site/index.html")
