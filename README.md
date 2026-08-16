# DifferentOdds API V2

A Python-based API and backend system for collecting, normalizing, and comparing sports betting odds across multiple sportsbooks in near real time.

https://api.differentodds.com/

## Overview

DifferentOdds API V2 aggregates and compares odds/pricing data across a wide range of markets and sources, maps it to a consistent internal format, and exposes it through an API. It's built to handle scheduled data collection, background processing, and persistent storage, with monitoring and alerting built in.

The system covers several different structures:

- **Daily Fantasy (DFS)** - Aggregates DFS odds (Underdog, Prizepicks, etc.)
- **Sportsbooks** - Aggregates sportsbook odds, including some Pay Per Head (PPH) books (Bet105, Ace, Metalic, etc.)
- **Esports Lines** - Collects odds specific to esports markets
- **Esports Differences** - Compares esports lines across multiple sources to determine discrepancies.
- **Same Game Parlay (SGP) Odds** - Collects and tracks SGP pricing across 10+ books (Fanduel, Draftkings, Betrivers, etc.)
- **Parlay RFQ (Request for Quote)** - Handles parlay pricing via RFQ-style requests (Novig, Prophetx)
- **Auto Same Game Parlay** - Automated scanning across hundreds of leg combinations to build/evaluate SGPs
- **Prediction Markets** - Collects data from prediction market platforms (4CX, Novig, etc.)
- **Prediction Market Comparisons** - Compares odds across prediction markets

## Features

- **Multi-Source Data Aggregation** - Collects and normalizes data across DFS, sportsbooks, esports, SGPs, and prediction markets into a  internal format
- **Odds/Price Comparison Engine** - Compares data across sources to identify differences (e.g., esports line differences, prediction market comparisons)
- **Auto SGP Scanning** - Automated scanning of hundreds of same game parlay leg combinations
- **Parlay RFQ Handling** - Support for request-for-quote style parlay pricing
- **Scheduled Jobs** - Recurring data pulls and maintenance tasks via APScheduler and cron jobs
- **Background Task Processing** - Asynchronous/distributed task handling with Celery and Redis
- **REST API** - FastAPI API layer for serving aggregated data
- **Database Layer** - Storing team/player data (Postgres)
- **Monitoring & Alerting** - Error tracking (Sentry) and notification support (Discord webhooks)
- **Authentication** - Auth handling for API access
- **Automated Tests** - Test suite covering core functionality

## Tech Stack

- **Language:** Python
- **API Framework:** FastAPI + Uvicorn/Gunicorn
- **Task Queue / Scheduling:** Celery, APScheduler, Redis
- **Database:** PostgreSQL
- **Web Scraping / Automation:** Playwright, Selenium (SeleniumBase)
- **Monitoring:** Sentry
- **Testing:** Pytest


## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL
- Redis

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Hurteau101/DifferentOdds-API-V2.git
   cd DifferentOdds-API-V2
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv/scripts/activate / Linux - venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables (database connection, Redis, API keys, etc.) as needed for your setup.

5. Run the API:
   ```bash
   uvicorn API.main:app --reload
   ```
   (Adjust the module path above to match your actual FastAPI app entry point.)

