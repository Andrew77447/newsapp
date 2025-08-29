#!/usr/bin/env python3
"""
News Headlines App with NewsData.io Official Python Client:
Terminal UI or Flask Web UI Inspired by wttr.in
"""

import os
from newsdataapi import NewsDataApiClient
from flask import Flask, request, render_template_string, Response
from rich.console import Console
from rich.table import Table
from rich.text import Text
from dotenv import load_dotenv

load_dotenv()  # Load .env file for API key

API_KEY = os.getenv("NEWSDATA_API_KEY")
if not API_KEY:
    raise RuntimeError("NEWSDATA_API_KEY not found in environment. Please create a .env file.")

app = Flask(__name__)
console = Console()

api_client = NewsDataApiClient(apikey=API_KEY)

VALID_CATEGORIES = {
    "business", "entertainment", "general",
    "health", "science", "sports", "technology"
}

VALID_COUNTRY_CODES = {
    "us", "gb", "ca", "de", "fr", "ro", "in", "au", "cn", "jp", "kr", "za", "br", "mx"
}

def sanitize_category(cat):
    if cat and cat.lower() in VALID_CATEGORIES:
        return cat.lower()
    return None

def sanitize_country(code):
    if code:
        c = code.strip().lower()
        if c in VALID_COUNTRY_CODES:
            return c
    return None

def fetch_headlines(category=None, language="en", country=None, limit=10):
    category = sanitize_category(category)
    country = sanitize_country(country)

    params = {
        "language": language or "en",
        "category": category,
    }

    if country:
        params["country"] = country

    params = {k: v for k, v in params.items() if v}

    try:
        response = api_client.latest_api(**params)
    except Exception as e:
        return None, f"Error fetching news: {e}"

    if response.get("status") != "success":
        return None, f"API error: {response.get('message', 'Unknown error')}"

    results = response.get("results", [])
    return results[:limit], None

def print_headlines_rich(articles):
    if not articles:
        console.print("[bold red]No news articles found matching your criteria.[/bold red]")
        return

    table = Table(title="Latest News Headlines", style="cyan", show_lines=True)
    table.add_column("#", justify="right", style="bold yellow", width=3)
    table.add_column("Title", style="bold white")
    table.add_column("Source", style="magenta")
    table.add_column("Published At", style="green", no_wrap=True)

    for i, article in enumerate(articles, 1):
        title = article.get("title", "No title")
        source = article.get("source_id", "Unknown source")
        pub_date = article.get("pubDate", "Unknown date")
        table.add_row(str(i), title, source, pub_date)

    console.print(table)

    console.print("\n[bold underline]URLs:[/bold underline]")
    for i, article in enumerate(articles, 1):
        url = article.get("link")
        if url:
            console.print(f"{i}. ", Text(url, style="blue underline"))

def run_terminal_mode(category=None, language="en", country=None, limit=10):
    articles, error = fetch_headlines(category, language, country, limit)
    if error:
        console.print(f"[bold red]{error}[/bold red]")
        return

    if console.is_terminal:
        print_headlines_rich(articles)
    else:
        print("No terminal detected, cannot display rich UI.")

@app.route("/")
def news():
    category = request.args.get("category")
    language = request.args.get("language", "en")
    country = request.args.get("country")
    limit = request.args.get("limit", default=10, type=int)
    limit = max(1, min(limit, 100))

    articles, error = fetch_headlines(category, language, country, limit)
    if error:
        return f"<h3>Error: {error}</h3>", 500

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <title>News Headlines</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            ul { list-style-type: none; padding: 0; }
            li { margin-bottom: 15px; }
            a { font-size: 1.1em; color: #007acc; text-decoration: none; }
            a:hover { text-decoration: underline; }
            small { color: #555; }
        </style>
    </head>
    <body>
        <h1>Latest News Headlines</h1>
        <ul>
        {% for article in articles %}
          <li>
            <a href="{{ article.link }}" target="_blank" rel="noopener noreferrer">{{ article.title }}</a><br/>
            <small>Source: {{ article.source_id }}</small>
          </li>
        {% endfor %}
        </ul>
    </body>
    </html>
    """
    return Response(render_template_string(html, articles=articles), mimetype="text/html")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NewsData.io Headlines App: Terminal & Web UI")
    parser.add_argument("--category", help="News category (business, entertainment, general, health, science, sports, technology)")
    parser.add_argument("--language", default="en", help="Language of news (en, etc.)")
    parser.add_argument("--country", help="Country code (2 letters, e.g. us, gb, ro)")
    parser.add_argument("--limit", type=int, default=10, help="Number of headlines to fetch (max 100)")
    parser.add_argument("--web", action="store_true", help="Run as Flask web server")

    args = parser.parse_args()

    if args.web:
        app.run(host="0.0.0.0", port=8000, debug=True)
    else:
        run_terminal_mode(args.category, args.language, args.country, args.limit)
