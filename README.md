# Warm Workcation Tracker

A live comparison of low-cost 28-night winter workcations from Dublin for one remote worker.

## Rules

- Dublin departure, one adult, 28 nights
- January or February 2027
- Typical daytime high of at least 18°C
- Private room only—shared rooms and dorms are excluded
- Exact dated Ryanair return fare plus exact whole-stay Hostelworld total
- Remote-work claims require explicit Wi-Fi/workspace evidence
- Private rooms without work evidence are shown as leads, never as work-ready

## Run

```bash
python monitor.py
python -m unittest discover -s tests -v
```

No secrets or third-party Python packages are required. GitHub Actions refreshes the public data daily. Prices are observations, not reservations; passport, visa, tax, and employer remote-work rules must be checked before booking.
