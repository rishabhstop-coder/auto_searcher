import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
from duckduckgo_search import DDGS
import sqlite3

# ==============================
# CONFIG
# ==============================

st.set_page_config(page_title="Lead Finder", layout="wide")

BLOCKED_DOMAINS = [
    "facebook","linkedin","instagram","youtube","twitter","x",
    "wikipedia","amazon","zillow","realtor","yelp","indeed",
    "glassdoor","tripadvisor","pinterest","github",
    "google","bing","apple","microsoft","reddit"
]

DORKS = [
    'site:{tld} "{genre}" "contact"',
    'site:{tld} "{genre}" "call us"',
    'site:{tld} "{genre}" "about us"',
    'site:{tld} "{genre}" "services"',
    'site:{tld} "{genre}" "our team"',
    'site:{tld} "{genre}" "family owned"',
    'site:{tld} "{genre}" "established"',
]

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}"

country_tlds = {
    "US": ".us", "CA": ".ca", "EU": ".eu",
    "UK": ".co.uk", "AU": ".com.au"
}

# ==============================
# DATABASE
# ==============================

def init_db():
    conn = sqlite3.connect("leads.db")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        url TEXT PRIMARY KEY,
        email TEXT,
        score INTEGER
    )
    """)
    conn.close()

def get_existing_urls():
    conn = sqlite3.connect("leads.db")
    try:
        df = pd.read_sql("SELECT url FROM leads", conn)
        return set(df["url"].tolist())
    except:
        return set()
    finally:
        conn.close()

def save_leads(df):
    conn = sqlite3.connect("leads.db")
    df.to_sql("leads", conn, if_exists="append", index=False)
    conn.close()

# ==============================
# HELPERS
# ==============================

def is_blocked(url):
    domain = urlparse(url).netloc.lower()
    return any(b in domain for b in BLOCKED_DOMAINS)

def extract_email(text):
    emails = re.findall(EMAIL_REGEX, text)
    return emails[0] if emails else ""

# ==============================
# SEARCH
# ==============================

def get_urls(genre, countries, existing):
    urls = set()
    random.shuffle(DORKS)

    with DDGS() as ddgs:
        for c in countries:
            tld = country_tlds.get(c, ".com")

            for dork in DORKS:
                query = dork.format(tld=tld, genre=genre)

                try:
                    results = ddgs.text(query, max_results=30)

                    for r in results:
                        u = r["href"]

                        if (
                            not is_blocked(u)
                            and u not in existing
                            and u not in urls
                        ):
                            urls.add(u)

                except:
                    pass

                time.sleep(random.uniform(1, 2.5))

    return list(urls)

# ==============================
# AUDIT
# ==============================

def audit(url):
    try:
        if not url.startswith("http"):
            url = "https://" + url

        r = requests.get(url, timeout=8, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")

        score = 0

        if not url.startswith("https"):
            score += 3

        if not soup.find("meta", {"name":"viewport"}):
            score += 3

        if len(soup.find_all("table")) > 5:
            score += 2

        text = soup.get_text().lower()

        if re.search(r"©\s*(200\d|201[0-6])", text):
            score += 2

        if score < 3:
            return None

        return {
            "url": url,
            "email": extract_email(r.text),
            "score": score
        }

    except:
        return None

# ==============================
# UI
# ==============================

st.title("🚀 Lead Generator")

genre = st.text_input("Business Type", "dental")
countries = st.multiselect("Countries", ["US","CA","EU","UK","AU"], default=["US"])

if st.button("Search Leads"):

    init_db()
    existing = get_existing_urls()

    urls = get_urls(genre, countries, existing)

    st.write(f"Found {len(urls)} new sites")

    results = []

    for u in urls:
        r = audit(u)
        if r:
            results.append(r)

    if results:
        df = pd.DataFrame(results).sort_values("score", ascending=False)

        st.dataframe(df)

        save_leads(df)

        st.success(f"{len(df)} leads saved (duplicates avoided automatically)")

    else:
        st.warning("No strong leads found")
