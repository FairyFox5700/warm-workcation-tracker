from __future__ import annotations

import json
import sys
import urllib.request
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "warm-workcation-tracker/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def flight_api(origin: str, destination: str, travel_date: str) -> str:
    return (
        "https://services-api.ryanair.com/farfnd/v4/oneWayFares"
        f"?departureAirportIataCode={origin}&arrivalAirportIataCode={destination}"
        f"&outboundDepartureDateFrom={travel_date}&outboundDepartureDateTo={travel_date}&currency=EUR"
    )


def stay_api(property_id: str, start: str, nights: int) -> str:
    return (
        "https://prod.apigee.hostelworld.com/legacy-hwapi-service/2.2/properties/"
        f"{property_id}/availability/?date-start={start}&num-nights={nights}"
        "&number-of-guests=1&application=web&currency=EUR"
    )


def parse_ryanair(outbound: dict[str, Any], inbound: dict[str, Any]) -> dict[str, Any]:
    first = outbound["fares"][0]["outbound"]
    second = inbound["fares"][0]["outbound"]
    return {
        "total_eur": round(float(first["price"]["value"]) + float(second["price"]["value"]), 2),
        "outbound": f'{first["flightNumber"]} · {first["departureDate"][11:16]}–{first["arrivalDate"][11:16]}',
        "return": f'{second["flightNumber"]} · {second["departureDate"][11:16]}–{second["arrivalDate"][11:16]}',
    }


def classify_room(name: str, kind: str) -> str:
    lower = name.lower()
    if kind == "privates" or "private" in lower or "single" in lower or "double" in lower:
        return "private"
    return "shared"


def parse_hostelworld(data: dict[str, Any]) -> dict[str, Any] | None:
    priced: list[tuple[float, str, str]] = []
    for kind in ("privates", "dorms"):
        for room in data.get("rooms", {}).get(kind, []):
            available = room.get("totalRoomsAvailable", 0) if kind == "privates" else room.get("totalBedsAvailable", 0)
            if not available:
                continue
            for total in room.get("totalPrice", []):
                priced.append((float(total["price"]["value"]), room.get("name", "Unknown room"), kind))
    if not priced:
        return None
    total, name, kind = min(priced, key=lambda row: row[0])
    return {"total_eur": round(total, 2), "room_name": name, "room_type": classify_room(name, kind)}


def clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def score_offer(offer: dict[str, Any]) -> float:
    cost = 100 * clamp((1800 - offer["total_eur"]) / 1200)
    review = 100 * clamp((offer["review_score"] - 7.5) / 2)
    warmth = 100 * clamp((offer["typical_high_c"] - 18) / 8)
    room = 85 if offer["room_type"] == "private" else 40
    return round(
        0.45 * cost + 0.25 * offer["work_score"] + 0.10 * offer["wifi_score"]
        + 0.08 * review + 0.05 * room + 0.07 * warmth,
        2,
    )


def build_offer(item: dict[str, Any], flight: dict[str, Any], stay: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    nights = (date.fromisoformat(item["return_date"]) - date.fromisoformat(item["outbound_date"])).days
    if nights != config["nights"]:
        raise ValueError(f"Expected {config['nights']} nights, got {nights}")
    total = round(flight["total_eur"] + stay["total_eur"], 2)
    work_ready = item["work_score"] >= config["minimum_work_score"] and item["wifi_score"] >= 55
    state = "verified" if work_ready else "lead"
    reason = "Exact price + work setup verified" if work_ready else "Exact price; work setup not verified"
    flight_url = (
        "https://www.ryanair.com/ie/en/fare-finder"
        f"?originIata={config['origin']}&destinationIata={item['airport']}&isReturn=true"
        f"&departureDateFrom={item['outbound_date']}&departureDateTo={item['outbound_date']}"
        f"&returnDateFrom={item['return_date']}&returnDateTo={item['return_date']}&budget=1800"
    )
    stay_url = (
        f"https://www.hostelworld.com/pwa/hosteldetails.php/property/{item['destination']}/{item['property_id']}"
        f"?from={item['outbound_date']}&to={item['return_date']}&guests=1&currency=EUR"
    )
    offer = {
        **item,
        "origin": config["origin"],
        "nights": nights,
        "month": item["outbound_date"][:7],
        "flight_total_eur": flight["total_eur"],
        "stay_total_eur": stay["total_eur"],
        "mandatory_fees_eur": 0.0,
        "total_eur": total,
        "room_name": stay["room_name"],
        "room_type": stay["room_type"],
        "outbound": flight["outbound"],
        "return": flight["return"],
        "state": state,
        "state_reason": reason,
        "flight_url": flight_url,
        "stay_url": stay_url,
        "price_quality": "exact",
    }
    offer["score"] = score_offer(offer)
    return offer


def choose_offers(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, ...], dict[str, Any]] = {}
    for offer in offers:
        key = (
            offer["origin"], offer["airport"], offer["outbound_date"], offer["return_date"],
            offer["property_id"], offer["room_name"].lower(),
        )
        old = unique.get(key)
        if old is None or offer["total_eur"] < old["total_eur"]:
            unique[key] = offer
    return sorted(unique.values(), key=lambda x: (x["state"] != "verified", -x["score"], x["total_eur"], x["id"]))


def render_card(deal: dict[str, Any], rank: int) -> str:
    badge = "BEST WORK VALUE" if rank == 1 and deal["state"] == "verified" else deal["state"].upper()
    month_name = "January" if deal["month"] == "2027-01" else "February"
    return f'''<article class="deal-card" data-testid="deal-card" data-id="{escape(deal['id'])}" data-state="{deal['state']}" data-month="{deal['month']}" data-room="{deal['room_type']}" data-total="{deal['total_eur']}">
<div class="card-top"><div><span class="badge {deal['state']}" data-testid="deal-status">{badge}</span><h2>{escape(deal['destination'])}, {escape(deal['country'])}</h2><p>{month_name} · {deal['nights']} nights · {deal['typical_high_c']}°C typical high</p></div><div class="total" data-testid="deal-total">€{deal['total_eur']:.2f}<small>flight + whole stay</small></div></div>
<div class="facts"><div><span>Stay</span><strong>€{deal['stay_total_eur']:.2f}</strong></div><div><span>Direct return</span><strong>€{deal['flight_total_eur']:.2f}</strong></div><div><span>Room</span><strong>{escape(deal['room_type'].title())}</strong></div><div><span>Work score</span><strong>{deal['work_score']}/100</strong></div></div>
<p class="work" data-testid="work-suitability"><strong>{escape(deal['workspace'])}</strong><br>{escape(deal['work_evidence'])}</p>
<details><summary>Dates, room and evidence</summary><div class="details"><p><strong>{deal['outbound_date']} → {deal['return_date']}</strong><br>{escape(deal['outbound'])}<br>{escape(deal['return'])}</p><p><strong>{escape(deal['property'])} · {deal['review_score']}/10</strong><br>{escape(deal['room_name'])}</p><p class="caveat">{escape(deal['state_reason'])}. Hostel listings can be noisy; check call privacy and employer policy before booking.</p><div class="links"><a data-testid="flight-link" target="_blank" rel="noopener noreferrer" href="{escape(deal['flight_url'])}">Flights ↗</a><a data-testid="stay-link" target="_blank" rel="noopener noreferrer" href="{escape(deal['stay_url'])}">Stay ↗</a><a target="_blank" rel="noopener noreferrer" href="{escape(deal['work_evidence_url'])}">Work evidence ↗</a><a target="_blank" rel="noopener noreferrer" href="{escape(deal['climate_url'])}">Climate ↗</a></div></div></details>
</article>'''


def render_index(deals: list[dict[str, Any]], checked_at: str, errors: list[dict[str, str]]) -> str:
    if not deals:
        raise ValueError("At least one live offer is required")
    cards = "".join(render_card(deal, i) for i, deal in enumerate(deals, 1))
    verified = sum(d["state"] == "verified" for d in deals)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Warm Workcation Tracker</title>
<style>
:root{{--bg:#08120f;--card:#10211b;--card2:#142a22;--text:#f5f7ef;--muted:#a7b8af;--line:#2c463b;--lime:#b9f35a;--cyan:#76e4d3;--amber:#ffd16b}}*{{box-sizing:border-box}}html{{background:var(--bg);color:var(--text);font:16px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}body{{margin:0}}main{{width:min(1120px,100%);margin:auto;padding:28px 18px 60px}}header{{padding:24px 0 18px}}.eyebrow{{color:var(--lime);font-weight:800;letter-spacing:.12em;text-transform:uppercase;font-size:.78rem}}h1{{font-size:clamp(2.35rem,7vw,5.4rem);line-height:.92;letter-spacing:-.06em;margin:.2em 0}}header p{{color:var(--muted);max-width:720px;font-size:1.08rem}}.summary{{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}}.stat{{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:9px 14px}}.stat strong{{color:var(--lime)}}.filters{{position:sticky;top:0;z-index:3;background:rgba(8,18,15,.94);backdrop-filter:blur(12px);display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;padding:12px 0;border-block:1px solid var(--line)}}label{{font-size:.75rem;color:var(--muted);font-weight:700}}select,input,button{{width:100%;min-height:44px;margin-top:4px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--text);padding:0 10px;font:inherit}}button{{cursor:pointer;color:var(--lime);font-weight:800}}#resultText{{margin:20px 0;color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}.deal-card{{min-width:0;background:linear-gradient(145deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:20px;padding:20px}}.deal-card:first-child{{border-color:var(--lime);box-shadow:0 0 0 1px #b9f35a35}}.card-top{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}}.badge{{display:inline-block;border-radius:999px;padding:5px 9px;background:#25392f;color:var(--cyan);font-size:.7rem;font-weight:900;letter-spacing:.08em}}.badge.lead{{color:var(--amber)}}h2{{margin:.6rem 0 .2rem;font-size:1.5rem}}.card-top p{{margin:0;color:var(--muted)}}.total{{color:var(--lime);font-size:1.8rem;font-weight:900;text-align:right;white-space:nowrap}}.total small{{display:block;color:var(--muted);font-size:.68rem;font-weight:600}}.facts{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:18px 0}}.facts div{{padding:10px;background:#08120f80;border-radius:10px;min-width:0}}.facts span,.facts strong{{display:block}}.facts span{{color:var(--muted);font-size:.7rem}}.facts strong{{font-size:.88rem;overflow-wrap:anywhere}}.work{{border-left:3px solid var(--cyan);padding-left:12px;color:var(--muted)}}.work strong{{color:var(--text)}}summary{{cursor:pointer;color:var(--cyan);font-weight:800;min-height:44px;padding-top:10px}}.details{{border-top:1px solid var(--line)}}.caveat{{color:var(--muted)}}.links{{display:flex;flex-wrap:wrap;gap:8px}}a{{color:var(--cyan)}}.links a{{background:#0a1813;border:1px solid var(--line);border-radius:9px;padding:9px 11px;text-decoration:none}}.empty{{display:none;background:var(--card);padding:24px;border-radius:16px}}footer{{margin-top:24px;padding:20px;background:var(--card);border:1px solid var(--line);border-radius:18px;color:var(--muted)}}footer strong{{color:var(--text)}}
@media(max-width:760px){{main{{padding:16px 12px 40px}}.filters{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}.card-top{{display:block}}.total{{text-align:left;margin-top:12px}}.facts{{grid-template-columns:1fr 1fr}}}}
@media(max-width:340px){{.filters{{grid-template-columns:1fr}}.facts{{grid-template-columns:1fr 1fr}}h1{{font-size:2.25rem}}}}
</style></head><body><main><header><div class="eyebrow">Winter 2026/27 · Dublin departure</div><h1>Trade grey<br>winter for sun.</h1><p>Exact 28-night flight + stay prices for a solo remote worker. Cheapest shared work-ready stays rank first; private rooms without verified desk/Wi-Fi stay clearly marked as leads.</p><div class="summary"><span class="stat"><strong>{verified}</strong> work-ready</span><span class="stat"><strong>{len(deals)}</strong> priced options</span><span class="stat"><strong>{len(errors)}</strong> source issues isolated</span></div></header>
<section class="filters" aria-label="Filters"><label>Month<select id="month"><option value="all">Any month</option><option value="2027-01">January</option><option value="2027-02">February</option></select></label><label>Room<select id="room"><option value="all">Any room</option><option value="private">Private</option><option value="shared">Shared</option></select></label><label>Status<select id="state"><option value="all">All prices</option><option value="verified">Work-ready only</option><option value="lead">Leads</option></select></label><label>Maximum total €<input id="budget" type="number" min="0" step="50" placeholder="No limit"></label></section><p id="resultText" aria-live="polite"></p><section class="grid" id="grid">{cards}</section><div class="empty" id="empty"><strong>No match.</strong> Try another month, shared rooms, or a higher maximum total.</div>
<footer><strong>How to read this</strong><p>“Verified” means an exact dated return fare, exact whole-stay 28-night price, and explicit Wi-Fi/workspace evidence were live when checked. “Lead” can have an exact price but lacks enough work evidence. Typical highs are climate normals, not forecasts. Prices exclude meals, local transport, baggage beyond the airline's basic allowance, and any unknown local fees.</p><p><strong>Before booking:</strong> check entry/visa rules for your passport, your employer’s cross-border remote-work policy, tax/social-security implications, call privacy, and backup internet.</p><small>Last live check: {escape(checked_at)}</small></footer></main>
<script>
const controls=[...document.querySelectorAll('#month,#room,#state,#budget')],cards=[...document.querySelectorAll('.deal-card')],text=document.querySelector('#resultText'),empty=document.querySelector('#empty');
function apply(){{const month=document.querySelector('#month').value,room=document.querySelector('#room').value,state=document.querySelector('#state').value,budget=Number(document.querySelector('#budget').value||Infinity);let n=0;cards.forEach(c=>{{const show=(month==='all'||c.dataset.month===month)&&(room==='all'||c.dataset.room===room)&&(state==='all'||c.dataset.state===state)&&Number(c.dataset.total)<=budget;c.hidden=!show;if(show)n++}});text.textContent=`${{n}} option${{n===1?'':'s'}} match`;empty.style.display=n?'none':'block';const q=new URLSearchParams();if(month!=='all')q.set('month',month);if(room!=='all')q.set('room',room);if(state!=='all')q.set('state',state);if(Number.isFinite(budget))q.set('max',budget);history.replaceState(null,'',q.size?'?'+q:'./')}}
const q=new URLSearchParams(location.search);if(q.get('month'))month.value=q.get('month');if(q.get('room'))room.value=q.get('room');if(q.get('state'))state.value=q.get('state');if(q.get('max'))budget.value=q.get('max');controls.forEach(c=>c.addEventListener('input',apply));apply();
</script></body></html>'''


def run(config_path: Path = ROOT / "config.json") -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    observations: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for item in config["candidates"]:
        try:
            outbound = fetch_json(flight_api(config["origin"], item["airport"], item["outbound_date"]))
            inbound = fetch_json(flight_api(item["airport"], config["origin"], item["return_date"]))
            flight = parse_ryanair(outbound, inbound)
            stay = parse_hostelworld(fetch_json(stay_api(item["property_id"], item["outbound_date"], config["nights"])))
            if stay is None:
                raise ValueError("No exact 28-night inventory")
            observations.append(build_offer(item, flight, stay, config))
        except Exception as exc:
            errors.append({"id": item["id"], "destination": item["destination"], "error": str(exc)})
    deals = choose_offers(observations)
    if not deals:
        raise RuntimeError(f"No live offers; source errors: {errors}")
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for deal in deals:
        deal["checked_at"] = checked_at
    payload = {"schema_version": "1.0", "checked_at": checked_at, "deals": deals, "source_errors": errors}
    (ROOT / "data.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (ROOT / "index.html").write_text(render_index(deals, checked_at, errors), encoding="utf-8")
    return payload


if __name__ == "__main__":
    try:
        result = run()
        print(json.dumps({"status": "ok", "offers": len(result["deals"]), "verified": sum(d["state"] == "verified" for d in result["deals"]), "errors": len(result["source_errors"])}))
    except Exception as error:
        print(json.dumps({"status": "error", "error": str(error)}), file=sys.stderr)
        raise
