import re
import subprocess
import tempfile
import wave

VOICES = {"ALEX": "en_US-ryan-medium", "SAM": "en_US-lessac-medium"}
PAUSE_SECONDS = 0.35

turns = []
for line in open("briefing.txt").read().splitlines():
    m = re.match(r"\s*\**(ALEX|SAM)\**\s*:\s*(.+)", line)
    if m:
        turns.append((m.group(1), m.group(2).strip()))
    elif turns and line.strip():
        turns[-1] = (turns[-1][0], turns[-1][1] + " " + line.strip())

if not turns:
    raise SystemExit("No ALEX/SAM lines found in briefing.txt")

for voice in VOICES.values():
    subprocess.run(["python", "-m", "piper.download_voices", voice], check=True)

with tempfile.TemporaryDirectory() as tmp, wave.open("briefing.wav", "wb") as out:
    for i, (speaker, text) in enumerate(turns):
        path = f"{tmp}/{i}.wav"
        subprocess.run(
            ["python", "-m", "piper", "-m", VOICES[speaker], "-f", path],
            input=text.encode(), check=True,
        )
        with wave.open(path, "rb") as w:
            if i == 0:
                out.setparams(w.getparams())
            rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
            out.writeframes(w.readframes(w.getnframes()))
        out.writeframes(b"\x00" * int(rate * PAUSE_SECONDS) * width * channels)

print(f"Wrote briefing.wav from {len(turns)} turns")
