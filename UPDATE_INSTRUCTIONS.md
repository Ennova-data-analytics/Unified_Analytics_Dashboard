# How to Update the Ennova ESADE Dashboard

## Quick Update (Recommended)
Open your terminal and run:

```
cd "/Users/jignesh/Desktop/Ennova/Social media dashboard"
claude "Read the update-dashboard.sh script in this folder and execute it step by step. Scrape ennova.esade Instagram account again using the same Apify actors (apify/instagram-scraper), process all data with the same analysis pipeline, and regenerate dashboard.html with all fresh data, metrics, and recommendations."
```

## What the update does:
1. Scrapes the latest profile data from ennova.esade
2. Scrapes all posts (up to 200 most recent)
3. Scrapes all reels (up to 100 most recent)
4. Runs the full analysis pipeline (engagement rates, scoring, classification)
5. Regenerates the dashboard HTML with all new data embedded
6. All charts, tables, recommendations, and insights are refreshed

## How often to update:
- Weekly for regular tracking
- After major campaigns or events
- Before strategy meetings
