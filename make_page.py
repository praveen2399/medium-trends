import html, os, datetime

os.makedirs("site", exist_ok=True)
today = datetime.date.today().strftime("%A, %B %d, %Y")
script = html.escape(open("briefing.txt").read()).replace("\n", " ")

links = ""
blocks = open("links.txt").read().strip().split("\n\n")
for b in blocks:
    title, url = b.split("\n")
    links += f' {html.escape(title)}'

page = f"""<!doctype html>"""

open("site/index.html", "w").write(page)