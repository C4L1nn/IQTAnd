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


def qpipe(cmds: list):
    r = requests.post(
        URL + "/pipeline",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=cmds,
        timeout=10,
    )
    r.raise_for_status()
    return [item.get("result") for item in r.json()]


def hlist(lst) -> dict:
    if not lst or not isinstance(lst, list):
        return {}
    return dict(zip(lst[::2], lst[1::2]))


def pct(a, b) -> str:
    return f"{a/b*100:.0f}%" if b else "-%"


now   = datetime.now(timezone.utc)
today = now.date().isoformat()

# ── Temel sayilar ───────────────────────────────────────────────────────────
total     = q(["SCARD", "iqt:all"]) or 0
today_ids = set(q(["SMEMBERS", f"iqt:day:{today}"]) or [])

hafta_ids: set[str] = set(today_ids)
for i in range(1, 7):
    hafta_ids.update(q(["SMEMBERS", f"iqt:day:{(now.date()-timedelta(days=i)).isoformat()}"]) or [])

# ── Retention ───────────────────────────────────────────────────────────────
def retention(days_ago: int) -> str:
    target_date = (now.date() - timedelta(days=days_ago)).isoformat()
    new_on_day  = set(q(["SMEMBERS", f"iqt:new:{target_date}"]) or [])
    if not new_on_day:
        return "veri yok"
    if days_ago == 1:
        came_back = new_on_day & today_ids
    else:
        window: set[str] = set()
        for i in range(days_ago):
            window.update(q(["SMEMBERS", f"iqt:day:{(now.date()-timedelta(days=i)).isoformat()}"]) or [])
        came_back = new_on_day & window
    return f"{pct(len(came_back), len(new_on_day))}  ({len(came_back)}/{len(new_on_day)})"

# ── Stream basari orani ─────────────────────────────────────────────────────
stream_today = hlist(q(["HGETALL", f"iqt:stream:{today}"]))
s_ok   = int(stream_today.get("ok",   0) or 0)
s_fail = int(stream_today.get("fail", 0) or 0)
s_total = s_ok + s_fail
stream_str = f"{s_ok}/{s_total}  ({pct(s_ok, s_total)} basarili)" if s_total else "henuz veri yok"

# ── Ortalama oturum suresi ─────────────────────────────────────────────────
sess_today = hlist(q(["HGETALL", f"iqt:sess:{today}"]))
sess_total = int(sess_today.get("total_sec", 0) or 0)
sess_count = int(sess_today.get("count",     0) or 0)
if sess_count:
    avg_min = sess_total / sess_count / 60
    sess_str = f"{avg_min:.1f} dakika  ({sess_count} oturum)"
else:
    sess_str = "henuz veri yok"

# ── Ozellik kullanimi (bugun) ───────────────────────────────────────────────
feat_today = hlist(q(["HGETALL", f"iqt:feat:{today}"]))

# ── Kullanici metadata (bugun aktifler) ────────────────────────────────────
os_c     = Counter()
lang_c   = Counter()
ver_c    = Counter()
screen_c = Counter()

if today_ids:
    metas = qpipe([["HGETALL", f"iqt:meta:{iid}"] for iid in today_ids])
    for raw in metas:
        m = hlist(raw)
        if not m:
            continue
        os_n = m.get("os", "?")
        os_v = m.get("os_v", "")
        os_c[f"{os_n} {os_v}".strip() if os_v else os_n] += 1
        lang_c[m.get("lang", "?")] += 1
        ver_c[m.get("ver", "?")] += 1
        if m.get("screen"):
            screen_c[m["screen"]] += 1


def row(label: str, value) -> None:
    print(f"  {label:<22} {value}")


def breakdown(counter: Counter, label: str) -> None:
    if not counter:
        return
    print(f"\n  {label}:")
    for k, v in counter.most_common(5):
        print(f"    {k:<22} {v}")


print()
print("=" * 46)
print("      iqtMusic Kullanim Istatistikleri")
print("=" * 46)

print("\n  [ GENEL ]")
row("Toplam kurulum", total)
row("Bugun aktif", len(today_ids))
row("Son 7 gun aktif", len(hafta_ids))

print("\n  [ RETENTION ]")
row("D1 (dun kuranlarin %si)", retention(1))
row("D7 (7 gun once kuranlarin %si)", retention(7))
row("D30 (30 gun once kuranlarin %si)", retention(30))

print("\n  [ PERFORMANS ]")
row("Stream basari (bugun)", stream_str)
row("Ort. oturum suresi", sess_str)

if feat_today:
    print("\n  [ OZELLIK KULLANIMI (bugun) ]")
    for feat, cnt in sorted(feat_today.items(), key=lambda x: -int(x[1])):
        print(f"    {feat:<22} {cnt}")

breakdown(ver_c,     "Versiyon (bugun aktif)")
breakdown(os_c,      "Isletim Sistemi")
breakdown(lang_c,    "Dil")
breakdown(screen_c,  "Ekran Cozunurlugu")

print("\n" + "=" * 46)
print()
