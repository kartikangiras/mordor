#!/usr/bin/env bash
# Fetch the persona pictures (PIVOT_PLAN.md Phase 10): the place each of the seven works, never a
# face. Six come from Wikimedia Commons under the licences listed below (credited in the README
# acknowledgements); Priya's is the Mordor mark. Writes web/public/avatars/<slug>.{jpg,png} as
# 256 px squares. Re-run to refresh.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=web/public/avatars; mkdir -p "$OUT"
UA='mordor-avatars/1.0 (https://github.com/kartikangiras/mordor)'

# slug|Commons file title|author|licence
PICKS=(
  'anita|File:Kendriya Vidyalaya 2 Salt Lake - Kolkata 2011-04-03 00188.jpg|Biswarup Ganguly|CC BY 3.0'
  'gurpreet|File:Paddy field in Punjab.jpg|Sarbjit Bahga|CC BY-SA 4.0'
  'rao|File:Delhi, India, Secretariat Building (Central Secretariat).jpg|Vyacheslav Argenberg|CC BY 4.0'
  'kapoor|File:Emergency building of Jagannath Gupta Institute of Medical Sciences and Hospital.jpg|Salil Kumar Mukherjee|CC BY-SA 4.0'
  'rekha|File:Residential area, Vaishali, Delhi.jpg|Nikhilb239|CC BY-SA 4.0'
  'mehta|File:Air quality monitor Yarraville.jpg|Oli.f28|CC BY-SA 4.0'
)

for row in "${PICKS[@]}"; do
  IFS='|' read -r slug title author lic <<<"$row"
  # the original's URL, through the Commons API (titles carry spaces and brackets)
  url=$(curl -sS -A "$UA" -G 'https://commons.wikimedia.org/w/api.php' --data-urlencode "titles=$title" --data 'action=query&format=json&prop=imageinfo&iiprop=url&iiurlwidth=1200' | python3 -c 'import json,sys; p=list(json.load(sys.stdin)["query"]["pages"].values())[0]; print(p["imageinfo"][0].get("thumburl") or p["imageinfo"][0]["url"])')
  curl -sS -A "$UA" -o "$OUT/$slug.raw" "$url"
  python3 - "$OUT/$slug.raw" "$OUT/$slug.jpg" <<'PY'
import sys
from PIL import Image, ImageOps
im = Image.open(sys.argv[1]).convert('RGB')
ImageOps.fit(im, (256, 256), Image.LANCZOS, centering=(0.5, 0.45)).save(sys.argv[2], 'JPEG', quality=82, optimize=True)
PY
  rm -f "$OUT/$slug.raw"
  echo "$slug.jpg <- $title ($lic)"
done

# Priya works at Mordor: the mark, on ink, as a square
python3 - <<'PY'
from PIL import Image
m = Image.open('web/public/brand/mark-192.png').convert('RGBA')
bg = Image.new('RGBA', (256, 256), (17, 21, 26, 255))
m.thumbnail((190, 190)); bg.alpha_composite(m, ((256 - m.width) // 2, (256 - m.height) // 2))
bg.convert('RGB').save('web/public/avatars/priya.png', 'PNG', optimize=True)
print('priya.png <- the Mordor mark')
PY

# the credits paragraph in the README acknowledgements
python3 - <<'PY'
import pathlib, re
picks = [
    ('anita', 'File:Kendriya Vidyalaya 2 Salt Lake - Kolkata 2011-04-03 00188.jpg', 'Biswarup Ganguly', 'CC BY 3.0'),
    ('gurpreet', 'File:Paddy field in Punjab.jpg', 'Sarbjit Bahga', 'CC BY-SA 4.0'),
    ('rao', 'File:Delhi, India, Secretariat Building (Central Secretariat).jpg', 'Vyacheslav Argenberg', 'CC BY 4.0'),
    ('kapoor', 'File:Emergency building of Jagannath Gupta Institute of Medical Sciences and Hospital.jpg', 'Salil Kumar Mukherjee', 'CC BY-SA 4.0'),
    ('rekha', 'File:Residential area, Vaishali, Delhi.jpg', 'Nikhilb239', 'CC BY-SA 4.0'),
    ('mehta', 'File:Air quality monitor Yarraville.jpg', 'Oli.f28', 'CC BY-SA 4.0'),
]
credit = 'Persona pictures from Wikimedia Commons: ' + ' · '.join(f"{t.replace('File:', '')} by {a} ({l})" for _, t, a, l in picks) + ". Priya's is the Mordor mark."
p = pathlib.Path('README.md'); s = p.read_text()
s = re.sub(r'\nPersona pictures from Wikimedia Commons:[^\n]*\n', '\n', s)
anchor = 'domain. Built on AWS with the Strands Agents SDK.\n'
assert anchor in s
s = s.replace(anchor, anchor + credit + '\n')
p.write_text(s); print('README credits written')
PY
