import json
import unittest
from datetime import date
from pathlib import Path

from monitor import build_offer, choose_offers, parse_hostelworld, parse_ryanair, render_index


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "origin": "DUB", "nights": 28, "minimum_work_score": 60,
        }
        self.item = {
            "id": "agadir-test", "destination": "Agadir", "country": "Morocco", "airport": "AGA",
            "outbound_date": "2027-01-04", "return_date": "2027-02-01", "property_id": "1",
            "property": "Work Hostel", "review_score": 9.0, "typical_high_c": 20.0,
            "climate_url": "https://example.com/climate", "work_score": 75, "wifi_score": 80,
            "workspace": "Coworking", "work_evidence": "Wi-Fi and desk verified",
            "work_evidence_url": "https://www.hostelworld.com/hostels/p/1/work-hostel/",
        }
        self.flight = {"total_eur": 100.0, "outbound": "FR1 · 10:00–12:00", "return": "FR2 · 13:00–15:00"}
        self.stay = {"total_eur": 400.0, "room_name": "4 Bed Dorm", "room_type": "shared"}

    def test_parses_exact_round_trip_and_whole_stay(self):
        outbound = {"fares": [{"outbound": {"flightNumber": "FR1", "departureDate": "2027-01-04T10:00:00", "arrivalDate": "2027-01-04T12:00:00", "price": {"value": 40}}}]}
        inbound = {"fares": [{"outbound": {"flightNumber": "FR2", "departureDate": "2027-02-01T13:00:00", "arrivalDate": "2027-02-01T15:00:00", "price": {"value": 60}}}]}
        stay_data = {"rooms": {"dorms": [{"name": "4 Bed Dorm", "totalBedsAvailable": 2, "totalPrice": [{"price": {"value": "400"}}]}], "privates": []}}
        self.assertEqual(100.0, parse_ryanair(outbound, inbound)["total_eur"])
        self.assertEqual(400.0, parse_hostelworld(stay_data)["total_eur"])

    def test_total_is_flight_plus_whole_stay(self):
        offer = build_offer(self.item, self.flight, self.stay, self.config)
        self.assertEqual(500.0, offer["total_eur"])
        self.assertEqual(28, offer["nights"])
        self.assertEqual("verified", offer["state"])

    def test_private_room_alone_does_not_claim_work_ready(self):
        item = {**self.item, "work_score": 35, "wifi_score": 25, "workspace": "Not verified", "work_evidence": "Private room only"}
        stay = {**self.stay, "room_name": "Single Private", "room_type": "private"}
        offer = build_offer(item, self.flight, stay, self.config)
        self.assertEqual("lead", offer["state"])
        self.assertIn("not verified", offer["state_reason"])

    def test_deduplicates_same_inventory(self):
        offer = build_offer(self.item, self.flight, self.stay, self.config)
        pricier = {**offer, "flight_total_eur": 110, "total_eur": 510}
        selected = choose_offers([pricier, offer])
        self.assertEqual(1, len(selected))
        self.assertEqual(500.0, selected[0]["total_eur"])

    def test_config_scope_is_28_nights_jan_or_feb(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        for candidate in config["candidates"]:
            nights = (date.fromisoformat(candidate["return_date"]) - date.fromisoformat(candidate["outbound_date"])).days
            self.assertEqual(28, nights)
            self.assertIn(candidate["outbound_date"][:7], {"2027-01", "2027-02"})
            self.assertGreaterEqual(candidate["typical_high_c"], 18)

    def test_render_has_filters_safe_links_and_mobile_rule(self):
        offer = build_offer(self.item, self.flight, self.stay, self.config)
        html = render_index([offer], "2026-10-25T08:00:00+00:00", [])
        self.assertIn('id="month"', html)
        self.assertIn('data-testid="deal-card"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn('@media(max-width:340px)', html)
        self.assertIn('private rooms without verified desk/Wi-Fi', html)


if __name__ == "__main__":
    unittest.main()
