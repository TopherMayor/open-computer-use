## 2026-05-01: Google Flights LAX→SJD — cabo

- **URL tested**: `https://www.google.com/travel/flights/search?tfs=...&q=LAX+to+SJD`
- **Flights found**: 2 prices
- **Cheapest price**: 300
- **Airline detected**: Alaska
- **Bot detection**: none
- **Screenshot**: /tmp/gsd-travel-learner-1274924/cabo_flights.png


- **URL tested**: `https://www.google.com/travel/flights/search?tfs=...&q=LAX+to+SJD`
- **Flights found**: none
- **Cheapest price**: N/A
- **Airline detected**: unknown
- **Bot detection**: none
- **Screenshot**: /tmp/gsd-travel-learner-1274580/cabo_flights.png

# Travel Scraping Learnings

Auto-generated learnings from the gsd-travel-automation cron job.
Each entry captures what worked, what failed, and how to improve.

---

**Setup completed:**
- ✅ gsd-computer-use cloned and installed from Gitea
- ✅ gsd-browser v0.1.21 installed (needs Chrome — not available on RPi)
- ✅ Camofox anti-detect browser running at localhost:9377
- ✅ Hermes browser tool confirmed working for Google Flights

**Key findings:**
- Camofox is the PRIMARY browser automation tool — already running with anti-detect
- gsd-browser requires Chrome which isn't installed (apt install times out)
- Hermes `browser_navigate()` + `browser_snapshot()` bypasses bot detection on Google Flights
- gsd-computer-use MCP server installed for desktop automation (not directly used for web scraping)

**Bot detection status:**
- Google Flights: ✅ Works via browser_navigate + snapshot
- Google Hotels: ✅ Works via browser_navigate + snapshot
- Kayak: ⚠️ Heavily blocked — use Camofox + vision fallback
- Expedia: ⚠️ Blocks aggressively even with Camofox

**Next steps for improvement:**
1. Install Chromium via snap or direct binary download
2. Test gsd-browser with Chrome once available
3. Add residential proxies to Camofox for harder sites
4. Add cruise line sites (Costco Travel, Princess) to scraping rotation