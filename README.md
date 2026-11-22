# Warm Workcation Tracker

A live comparison of low-cost 28-night winter workcations from Dublin for one remote worker.

## Rules

- Dublin departure, one adult, 28 nights
- January or February 2027
- Typical daytime high of at least 18°C
- Private room only—shared rooms and dorms are excluded
- Exact dated Ryanair return fare plus exact whole-stay Hostelworld total
- Remote-work claims require explicit Wi-Fi/workspace evidence
- Ukrainian-passport entry rules from official Moroccan, Spanish, and EU sources
- Private rooms without work evidence are shown as leads, never as work-ready

## Run

```bash
python monitor.py
python -m unittest discover -s tests -v
```

No secrets or third-party Python packages are required. GitHub Actions refreshes the public data daily. Prices are observations, not reservations; passport, visa, tax, and employer remote-work rules must be checked before booking.

## Additional manual research resources

`monitor.py` only automates two sources: Ryanair's public fare API and Hostelworld's public availability API, because both can be
queried without logging in and without violating their terms of use. Marketplaces that require an account, a CAPTCHA, or forbid
scraping in their terms (Facebook Marketplace, Airbnb, Booking.com, and most classifieds sites) are **not** queried automatically —
treat anything found there the same way this tracker treats a "lead": real but not independently verified, so check the live
listing yourself before paying.

Use these to widen the search by hand, especially for monthly flatshares and private landlords, which rarely appear on Hostelworld:

**Room rentals / flatshares**

| Site | What to search for |
| --- | --- |
| [Facebook Marketplace](https://www.facebook.com/marketplace/) | Private rooms, monthly rentals, local groups (e.g. "Agadir expats" or "Taghazout surf housing") |
| [SpareRoom](https://www.spareroom.com/) | Rooms in shared apartments |
| [Badi](https://www.badi.com/) | Furnished rooms and flatshares (strong in Spain) |
| [Idealista](https://www.idealista.com/) | Rooms and flats in Spain |
| [Avito.ma](https://www.avito.ma/) | Moroccan rental listings, including Agadir/Marrakech private rooms |
| [Sahibinden](https://www.sahibinden.com/) | Rooms and apartments in Turkey, if Antalya-style routes are considered |

**Flights from Dublin (cross-check against the live Ryanair fare used here)**

| Site | Purpose |
| --- | --- |
| [Google Flights](https://www.google.com/travel/flights) | Compare dates and destinations side by side |
| [Skyscanner](https://www.skyscanner.ie/) | Cheapest return fares, including connecting itineraries |
| [Kiwi.com](https://www.kiwi.com/) | Alternative/connecting routes Ryanair doesn't sell directly |
| [Ryanair](https://www.ryanair.com/) | Same source this tracker's live fares come from — verify before booking |
| [easyJet](https://www.easyjet.com/) | Budget alternative on routes Ryanair doesn't serve |

**Monthly accommodation platforms**

| Site | Purpose |
| --- | --- |
| [Booking.com](https://www.booking.com/) | Monthly apartment and guesthouse rates, often with long-stay discounts |
| [Airbnb](https://www.airbnb.com/) | 28+ night discounts on entire places or private rooms |
| [HousingAnywhere](https://www.housinganywhere.com/) | Medium-term furnished rentals aimed at students/remote workers |
| [Uniplaces](https://www.uniplaces.com/) | Furnished rooms, mainly in Europe |

For a strict budget (e.g. around €500 all-in), local Facebook rental groups and direct monthly negotiations with a landlord
typically beat platform listings — but they can't be verified automatically, so confirm the room, Wi-Fi, and cancellation terms
directly with the host before transferring any money.
