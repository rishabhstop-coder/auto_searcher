import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
import sqlite3

# SAFE IMPORT (works everywhere)
try:
    from duckduckgo_search import DDGS
except:
    from ddgs import DDGS

# ==============================
# CONFIG
# ==============================

st.set_page_config(page_title="Lead Generator", layout="wide")

country_tlds = {
    "US": ".us",
    "CA": ".ca",
    "EU": ".eu",
    "UK": ".co.uk",
    "AU": ".com.au"
}

BLOCKED_DOMAINS = [
    "facebook","linkedin","instagram","youtube","twitter","x",
    "wikipedia","amazon","zillow","realtor","yelp","indeed",
    "glassdoor","tripadvisor","pinterest","github",
    "google","bing","apple","microsoft","reddit",
    "yellowpages","mapquest","bbb","angi","houzz","manta"
]

DORKS = [
    'site:{tld} "{genre}" contact',
    'site:{tld} "{genre}" "contact us"',
    'site:{tld} "{genre}" "call us"',
    'site:{tld} "{genre}" "about us"',
    'site:{tld} "{genre}" services',
    'site:{tld} "{genre}" "our team"',
    '"{genre}" "contact us" site:{tld}',
]

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}"

# ==============================
# DATABASE
# ==============================

def init_db():
    conn = sqlite3.connect("leads.db")
    conn.execute("CREATE TABLE IF NOT EXISTS urls (url TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

def get_existing_urls():
    conn = sqlite3.connect("leads.db")
    try:
        rows = conn.execute("SELECT url FROM urls").fetchall()
        return set([r[0] for r in rows])
    except:
        return set()
    finally:
        conn.close()

def save_urls(urls):
    conn = sqlite3.connect("leads.db")
    for u in urls:
        try:
            conn.execute("INSERT INTO urls (url) VALUES (?)", (u,))
        except:
            pass
    conn.commit()
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

def get_dorked_urls(genre, countries, existing_urls):

    urls = set()
    random.shuffle(DORKS)

    with DDGS() as ddgs:
        for country in countries:
            tld = country_tlds.get(country, ".com")

            for dork in DORKS:
                query = dork.format(tld=tld, genre=genre)

                try:
                    results = ddgs.text(query, max_results=40)

                    for r in results:
                        url = r.get("href")

                        if not url:
                            continue

                        if (
                            not is_blocked(url)
                            and url not in existing_urls
                            and url not in urls
                        ):
                            urls.add(url)

                except:
                    pass

                time.sleep(random.uniform(1, 2))

    return list(urls)

# ==============================
# AUDIT
# ==============================

def audit_site(url):

    data = {
        "url": url,
        "email": "",
        "load_time": 0,
        "ssl_issue": False,
        "mobile_issue": False,
        "speed_issue": False,
        "outdated_site": False,
        "tech_stack": "Unknown",
        "pitch_score": 0
    }

    try:
        if not url.startswith("http"):
            url = "http://" + url

        if not url.startswith("https"):
            data["ssl_issue"] = True
            data["pitch_score"] += 3

        start = time.time()

        response = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        load_time = time.time() - start
        data["load_time"] = round(load_time, 2)

        if load_time > 4:
            data["speed_issue"] = True
            data["pitch_score"] += 2

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text().lower()

        data["email"] = extract_email(response.text)

        if not soup.find("meta", attrs={"name": "viewport"}):
            data["mobile_issue"] = True
            data["pitch_score"] += 4

        tables = soup.find_all("table")
        divs = soup.find_all("div")

        if len(tables) > 5 and len(divs) < 20:
            data["tech_stack"] = "Table Layout"
            data["pitch_score"] += 2

        if re.search(r"©\s*(200\d|201[0-6])", text):
            data["outdated_site"] = True
            data["pitch_score"] += 2

        if ".swf" in text:
            data["tech_stack"] = "Flash"
            data["pitch_score"] += 5

        if data["pitch_score"] < 3:
            return None

        return data

    except:
        return None

# ==============================
# UI
# ==============================

st.title("🚀 Website Revamp Lead Generator")

genre = st.text_input("Business Type", "dental")

countries = st.multiselect(
    "Select Countries",
    ["US", "CA", "EU", "UK", "AU"],
    default=["US"]
)

if st.button("🔍 Search Leads"):

    if not genre or not countries:
        st.warning("Please enter genre and select countries")
        st.stop()

    init_db()
    existing_urls = get_existing_urls()

    with st.spinner("Searching for new websites..."):
        urls = get_dorked_urls(genre, countries, existing_urls)

    st.info(f"Found {len(urls)} new websites (duplicates skipped)")

    save_urls(urls)

    leads = []
    progress = st.progress(0)

    for i, url in enumerate(urls):
        report = audit_site(url)

        if report:
            leads.append(report)

        progress.progress((i + 1) / len(urls))

    if leads:
        df = pd.DataFrame(leads)
        df = df.sort_values(by="pitch_score", ascending=False)

        st.success(f"Found {len(leads)} strong leads")
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode()
        st.download_button("📥 Download CSV", csv, "leads.csv", "text/csv")

    else:
        st.warning("No strong leads found. Try another niche.")
