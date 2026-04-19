#!/usr/bin/env python3
"""iqtMusic kullanim istatistikleri — python stats.py"""
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

URL   = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip()
TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()

if not URL or not TOKEN:
    print("Eksik env var: UPSTASH_REDIS_REST_URL ve UPSTASH_REDIS_REST_TOKEN")
    sys.exit(1)


def q(cmd: list):
    r = requests.post(URL, headers={"Authorization": f"Bearer {TOKEN}"}, json=cmd, timeout=5)
    r.raise_for_status()
    return r.json().get("result")


def qpipe(cmds: list[list]):
    r = requests.post(
        URL + "/pipeline",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=cmds,
        timeout=10,
    )
    r.raise_for_status()
    return [item.get("result") for item in r.json()]


def hlist_to_dict(lst) -> dict:
    if not lst or not isinstance(lst, list):
        return {}
    return dict(zip(lst[::2], lst[1::2]))


now   = datetime.now(timezone.utc)
today = now.date().isoformat()

total      = q(["SCARD", "iqt:all"]) or 0
today_ids  = q(["SMEMBERS", f"iqt:day:{today}"]) or []

hafta_ids: set[str] = set(today_ids)
for i in range(1, 7):
    gun = (now.date() - timedelta(days=i)).isoformat()
    hafta_ids.update(q(["SMEMBERS", f"iqt:day:{gun}"]) or [])

# Metadata: bugün aktif kullanicilarin detaylari
os_c      = Counter()
os_ver_c  = Counter()
lang_c    = Counter()
ver_c     = Counter()
screen_c  = Counter()

if today_ids:
    metas = qpipe([["HGETALL", f"iqt:meta:{iid}"] for iid in today_ids])
    for raw in metas:
        m = hlist_to_dict(raw)
        if not m:
            continue
        os_str = m.get("os", "?")
        os_v   = m.get("os_v", "")
        os_c[f"{os_str} {os_v}".strip() if os_v else os_str] += 1
        lang_c[m.get("lang", "?")] += 1
        ver_c[m.get("ver", "?")] += 1
        if m.get("screen"):
            screen_c[m["screen"]] += 1


def show_breakdown(counter: Counter, label: str):
    if not counter:
        return
    print(f"\n  {label}:")
    for k, v in counter.most_common(5):
        print(f"    {k:<20} {v}")


print()
print("=" * 40)
print("    iqtMusic Kullanim Istatistikleri")
print("=" * 40)
print(f"  Toplam kurulum    : {total}")
print(f"  Bugun aktif       : {len(today_ids)}")
print(f"  Son 7 gun aktif   : {len(hafta_ids)}")
show_breakdown(ver_c,     "Versiyon")
show_breakdown(os_c,      "İsletim Sistemi")
show_breakdown(lang_c,    "Dil")
show_breakdown(screen_c,  "Ekran Cozunurlugu")
print("=" * 40)
print()
