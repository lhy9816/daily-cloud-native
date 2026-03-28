import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import feedparser
from datetime import datetime, timedelta, timezone
import time

cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
print(f"Cutoff: {cutoff}")
print()

f = feedparser.parse("https://www.cncf.io/feed/")
print(f"CNCF feed: {len(f.entries)} entries")
for e in f.entries[:5]:
    parsed = e.get("published_parsed") or e.get("updated_parsed")
    ts = time.mktime(parsed) if parsed else None
    dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
    if dt:
        within = dt >= cutoff
        print(f"  {dt} | within_24h={within} | {e.get('title','?')[:70]}")
    else:
        print(f"  NO TIME | {e.get('title','?')[:70]}")

print()
print("=== Kubernetes blog ===")
f2 = feedparser.parse("https://kubernetes.io/blog/feed.xml")
print(f"K8s feed: {len(f2.entries)} entries")
print(f"K8s feed status: {f2.get('status', '?')}")
print(f"K8s feed version: {f2.get('version', '?')}")
if f2.bozo:
    print(f"K8s feed bozo: {f2.bozo_exception}")

print()
print("=== ArXiv ===")
import httpx
params = {
    "search_query": "cat:cs.DC OR all:kubernetes OR all:inference",
    "start": 0,
    "max_results": 5,
    "sortBy": "submittedDate",
    "sortOrder": "descending",
}
r = httpx.get("https://export.arxiv.org/api/query", params=params, timeout=30)
print(f"Status: {r.status_code}")
import xml.etree.ElementTree as ET
ns = {"atom": "http://www.w3.org/2005/Atom"}
root = ET.fromstring(r.text)
entries = root.findall("atom:entry", ns)
print(f"Entries: {len(entries)}")
for e in entries[:3]:
    t = (e.find("atom:title", ns).text or "").strip().replace("\n"," ")[:60]
    p = e.find("atom:published", ns).text if e.find("atom:published", ns) is not None else "?"
    print(f"  {p} | {t}")

print()
print("=== WeChat (RSSHub) ===")
try:
    r3 = httpx.get("http://localhost:1200/wechat/mp/article/cloud-native-lab", timeout=5)
    print(f"Status: {r3.status_code}")
except Exception as e:
    print(f"Error: {e}")
