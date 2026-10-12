import urllib.request, re, json

req = urllib.request.Request('https://www.youtube.com/@LofiGirl/streams', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')

# Find videoIds with BADGE_STYLE_TYPE_LIVE_NOW or style="LIVE"
vids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
unique_vids = []
for v in vids:
    if v not in unique_vids:
        unique_vids.append(v)

print(f"Total video IDs found: {len(unique_vids)}")

for v in unique_vids[:10]:
    try:
        oreq = urllib.request.Request(f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={v}&format=json', headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(oreq, timeout=5)
        data = json.loads(res.read())
        title = data.get('title', '').encode('ascii', 'ignore').decode('ascii')
        print(f"ID: {v} | Title: {title}")
    except Exception as e:
        print(f"ID: {v} | Error: {e}")
