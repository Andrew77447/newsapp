#!/usr/bin/env python3
"""
News Headlines App with NewsData.io Official Python Client:
Terminal UI or Flask Web UI with Caching and Search.
"""

import os
import argparse
import logging
from datetime import datetime, timezone
from newsdataapi import NewsDataApiClient
from flask import Flask, request, render_template, Response
from rich.console import Console
from rich.table import Table
from rich.text import Text
from dotenv import load_dotenv
from cachelib import SimpleCache

# --- Configuration & Initialization ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_KEY = os.getenv("NEWSDATA_API_KEY")
if not API_KEY:
    raise RuntimeError("NEWSDATA_API_KEY not found in environment. Please create a .env file.")

app = Flask(__name__)
console = Console()
api_client = NewsDataApiClient(apikey=API_KEY)
cache = SimpleCache(threshold=500, default_timeout=600) # Cache for 10 minutes

VALID_CATEGORIES = {
    "business", "crime", "domestic", "education", "entertainment", "environment",
    "food", "health", "lifestyle", "other", "politics", "science", "sports",
    "technology", "top", "tourism", "world"
}
VALID_COUNTRY_CODES = {
    "us", "gb", "ca", "de", "fr", "ro", "in", "au", "cn", "jp", "kr", "za", "br", "mx"
}

# --- Core Logic ---

def format_date(date_string):
    """Formats an ISO date string into a user-friendly format."""
    if not date_string:
        return None
    try:
        # Works for formats like "2023-08-29 12:34:56"
        dt_object = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        return dt_object.astimezone().strftime('%d %b %Y, %H:%M')
    except (ValueError, TypeError):
        logging.warning(f"Could not parse date: {date_string}")
        return date_string

def fetch_headlines(q=None, category=None, country=None, language="en", limit=10):
    """Fetches news from API, with caching."""
    params = {
        "q": q,
        "category": category if category and category.lower() in VALID_CATEGORIES else None,
        "country": country if country and country.lower() in VALID_COUNTRY_CODES else None,
        "language": language or "en",
    }
    # Remove None values so they aren't sent to the API
    params = {k: v for k, v in params.items() if v}
    
    # Create a unique cache key based on the request parameters
    cache_key = f"news-{hash(frozenset(params.items()))}"
    cached_result = cache.get(cache_key)
    if cached_result:
        logging.info(f"Serving from cache for key: {cache_key}")
        return cached_result[:limit], None

    logging.info(f"Fetching from API with params: {params}")
    try:
        response = api_client.latest_api(**params)
    except Exception as e:
        logging.error(f"Error fetching from NewsData API: {e}")
        return None, f"Error communicating with the news service: {e}"

    if response.get("status") != "success":
        error_msg = f"API error: {response.get('results', {}).get('message', 'Unknown error')}"
        logging.error(error_msg)
        return None, error_msg

    results = response.get("results", [])
    for article in results:
        article['pubDate_formatted'] = format_date(article.get("pubDate"))

    cache.set(cache_key, results)
    return results[:limit], None

# --- Terminal UI (TUI) Mode ---

def print_headlines_rich(articles, query_info):
    """Prints news articles to the terminal using rich."""
    if not articles:
        console.print("[bold red]No news articles found matching your criteria.[/bold red]")
        return

    title = f"Latest News Headlines for: [bold cyan]{query_info}[/bold cyan]"
    table = Table(title=title, show_lines=True, header_style="bold magenta")
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Title", style="bold white", min_width=40)
    table.add_column("Source", style="yellow")
    table.add_column("Published At", style="green", no_wrap=True)

    for i, article in enumerate(articles, 1):
        table.add_row(
            str(i),
            article.get("title", "No title"),
            article.get("source_id", "Unknown"),
            article.get("pubDate_formatted", "Unknown date")
        )

    console.print(table)
    console.print("\n[bold underline]Links:[/bold underline]")
    for i, article in enumerate(articles, 1):
        if url := article.get("link"):
            console.print(f"{i}. ", Text(url, style="blue underline"))

def run_terminal_mode(args):
    """Runs the application in terminal mode."""
    query_parts = [args.query, args.category, args.country, args.language]
    query_info = ' | '.join(filter(None, query_parts)) or "General"
    
    articles, error = fetch_headlines(args.query, args.category, args.country, args.language, args.limit)
    
    if error:
        console.print(f"[bold red]ERROR:[/bold red] {error}")
        return

    if console.is_terminal:
        print_headlines_rich(articles, query_info)
    else:
        # Fallback for non-interactive terminals (e.g., piping output)
        if articles:
            for article in articles:
                print(f"- {article.get('title')}\n  {article.get('link')}\n")
        else:
            print("No news articles found.")


# --- Flask Web UI Mode ---

@app.route("/")
def news_web():
    """Flask route to display news in a web page."""
    params = {
        "q": request.args.get("q"),
        "category": request.args.get("category"),
        "country": request.args.get("country"),
        "language": request.args.get("language", "en"),
        "limit": request.args.get("limit", default=15, type=int)
    }
    params["limit"] = max(1, min(params["limit"], 100)) # Clamp limit
    
    articles, error = fetch_headlines(**params)
    
    return render_template(
        "index.html",
        articles=articles,
        error=error,
        params=params, # Pass params to pre-fill the form
        valid_categories=sorted(list(VALID_CATEGORIES)),
        valid_countries=sorted(list(VALID_COUNTRY_CODES))
    )

# --- Main Execution ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NewsData.io Headlines App: Terminal & Web UI",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-q", "--query", help="Search for a keyword or phrase.")
    parser.add_argument("-c", "--category", help="News category (e.g., technology, sports).")
    parser.add_argument("--country", help="Country code (2 letters, e.g., us, ro).")
    parser.add_argument("-l", "--language", default="en", help="Language of news (e.g., en, de, ro).")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Number of headlines to fetch.")
    parser.add_argument("--web", action="store_true", help="Run as a Flask web server.")
    
    args = parser.parse_args()

    if args.web:
        logging.info("Starting Flask web server on http://0.0.0.0:8000")
        app.run(host="0.0.0.0", port=8000, debug=False) # Debug=False for production
    else:
        run_terminal_mode(args)