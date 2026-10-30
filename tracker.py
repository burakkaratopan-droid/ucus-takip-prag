"""İzmir / İstanbul ⇄ Prag kısa gezi uçuş takipçisi (sadece aktarmasız uçuşlar).

Her çalıştırmada, tarih aralığındaki izin sınırına (config.json → max_leave) uyan
min_days–max_days günlük tüm gidiş-dönüş kombinasyonlarını (gidiş ve dönüş
günü dahil) Google Flights üzerinden tarar ve docs/data.json dosyasına ekler.
Panel (docs/index.html) bu dosyayı okur.

İzin sayımı: gidiş ve dönüş günü dahil her hafta içi günü 1 izin sayılır
(akşam uçuşu da olsa). Resmi tatiller izin yemez, bayram arifesi 0,5 sayılır.
"""

import json
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fast_flights import FlightQuery, Passengers, create_query, fetch_flights_html
from selectolax.lexbor import LexborHTMLParser

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
DATA_FILE = ROOT / "docs" / "data.json"


def leave_days(dep, ret):
    """Gidiş ve dönüş günü dahil kullanılacak izin günü sayısı."""
    holidays = {date.fromisoformat(h["date"]): h for h in CONFIG["public_holidays"]}
    total, d = 0.0, dep
    while d <= ret:
        h = holidays.get(d)
        if d.weekday() < 5:
            if h is None:
                total += 1
            elif h.get("half"):
                total += 0.5
        d += timedelta(days=1)
    return total


def combinations():
    """Tarih aralığında, izin sınırına uyan tüm gidiş-dönüş kombinasyonları (her kalkış havalimanı için)."""
    today = date.today()
    start = max(date.fromisoformat(CONFIG["date_from"]), today + timedelta(days=1))
    end = date.fromisoformat(CONFIG["date_to"])
    dep = start
    while dep <= end:
        for span in range(CONFIG["min_days"], CONFIG["max_days"] + 1):
            ret = dep + timedelta(days=span - 1)
            if ret > end:
                continue
            leave = leave_days(dep, ret)
            if leave <= CONFIG["max_leave"]:
                for o in CONFIG["origins"]:
                    yield o["code"], dep, ret, span, leave
        dep += timedelta(days=1)


def build_query(origin, dep, ret, max_stops=0):
    d = CONFIG["destination"]["code"]
    return create_query(
        flights=[
            FlightQuery(date=dep.isoformat(), from_airport=origin, to_airport=d),
            FlightQuery(date=ret.isoformat(), from_airport=d, to_airport=origin),
        ],
        trip="round-trip",
        seat="economy",
        passengers=Passengers(adults=CONFIG["adults"]),
        language="tr",
        currency=CONFIG["currency"],
        max_stops=max_stops,
    )


def parse(html):
    """Google Flights sayfasından gidiş seçeneklerini ve gidiş-dönüş toplam fiyatlarını çıkarır.

    fast-flights'ın kendi ayrıştırıcısı fiyatsız sonuçlarda çöktüğü ve sadece
    "en iyi uçuşlar" bloğunu okuduğu için burada kendi ayrıştırıcımızı kullanıyoruz.
    """
    node = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if node is None:
        raise RuntimeError("Google Flights beklenen veriyi döndürmedi (engellenmiş olabilir)")
    js = node.text()
    raw = js.split("data:", 1)[1].rsplit(",", 1)[0]
    if raw.endswith("errorHasStatus: true"):
        return []
    payload = json.loads(raw)

    options = []
    for block in (2, 3):
        rows = payload[block][0] if len(payload) > block and payload[block] else None
        for row in rows or []:
            try:
                price = row[1][0][1]
            except (IndexError, TypeError):
                continue
            if not price:
                continue
            flight = row[0]
            legs = []
            for s in flight[2]:
                dep_t = (s[8] or []) + [None, None]
                arr_t = (s[10] or []) + [None, None]
                legs.append({
                    "from": s[3],
                    "to": s[6],
                    "dep": f"{dep_t[0] or 0:02d}:{dep_t[1] or 0:02d}",
                    "arr": f"{arr_t[0] or 0:02d}:{arr_t[1] or 0:02d}",
                    "arr_date": "-".join(f"{x:02d}" for x in s[21]) if s[21] else None,
                    "minutes": s[11],
                })
            options.append({
                "price": int(price),
                "airlines": flight[1],
                "legs": legs,
                "minutes": flight[9] if len(flight) > 9 and isinstance(flight[9], int) else None,
            })
    options.sort(key=lambda x: x["price"])
    return options


def fetch(origin, dep, ret, attempts=3):
    q = build_query(origin, dep, ret, 0)
    err = None
    for i in range(attempts):
        try:
            options = parse(fetch_flights_html(q))
            # Google ara sıra boş sonuç döndürüyor; birkaç kez daha dene.
            if options or i == attempts - 1:
                return options, q.url()
        except Exception as e:  # ağ hatası, engelleme, değişen sayfa yapısı
            err = e
        time.sleep(5 * (i + 1) + random.random() * 3)
    raise err


def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"runs": [], "combos": {}}


def compact_option(o):
    if not o:
        return None
    return {
        "price": o["price"],
        "airlines": o["airlines"],
        "via": [leg["to"] for leg in o["legs"][:-1]],
        "legs": o["legs"],
        "minutes": o["minutes"],
    }


def main():
    data = load_data()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    data["runs"].append(now)
    run_idx = len(data["runs"]) - 1
    combos = list(combinations())
    ok = failed = 0

    for n, (origin, dep, ret, days, leave) in enumerate(combos, 1):
        key = f"{origin}_{dep.isoformat()}_{ret.isoformat()}"
        try:
            opts, url = fetch(origin, dep, ret)
            time.sleep(1 + random.random() * 2)
        except Exception as e:
            failed += 1
            print(f"[{n}/{len(combos)}] {key} HATA: {e}", file=sys.stderr)
            continue

        direct = next((o for o in opts if len(o["legs"]) == 1), None)
        entry = data["combos"].setdefault(key, {
            "origin": origin, "dep": dep.isoformat(), "ret": ret.isoformat(),
            "days": days, "history": [],
        })
        entry["leave"] = leave  # tatil listesi değişirse güncel kalsın
        # Google bazen boş döndürüyor: o zaman son bilinen fiyatı koru, "eski" diye işaretle.
        stale = {}
        if direct:
            entry["direct"] = compact_option(direct)
        elif entry.get("direct"):
            stale["direct"] = True
        entry["stale"] = stale

        point = [run_idx, entry["direct"]["price"] if entry.get("direct") else None]
        # Sadece fiyat değiştiğinde yeni nokta ekle; dosya küçük kalsın.
        if not entry["history"] or entry["history"][-1][1] != point[1]:
            entry["history"].append(point)
        entry["checked"] = run_idx
        entry["url"] = url
        ok += 1
        print(f"[{n}/{len(combos)}] {key} izin={leave} fiyat={point[1]}"
              + (f" (eski: {', '.join(stale)})" if stale else ""))

    data["updated"] = now
    data["config"] = CONFIG
    data["last_run"] = {
        "at": now, "ok": ok, "failed": failed, "total": len(combos),
        "stale": sum(1 for c in data["combos"].values() if c.get("checked") == run_idx and c["stale"]),
    }
    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Bitti: {ok} başarılı, {failed} hatalı / {len(combos)}")
    # Hepsi başarısızsa iş akışı kırmızı görünsün.
    sys.exit(1 if ok == 0 and combos else 0)


if __name__ == "__main__":
    main()
