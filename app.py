import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
import sqlite3

# safer import
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
    'site:{tld} "{genre}" "services"',
    'site:{tld} "{genre}" "our team"',
    'site:{tld} "{genre}" "family owned"',
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
# SEARCH (RESILIENT VERSION)
# ==============================

def get_dorked_urls(genre, countries, existing_urls):

    urls = set()
    random.shuffle(DORKS)

    with DDGS() as ddgs:

        for country in countries:
            tld = country_tlds.get(country, ".com")

            for dork in DORKS:
                query = dork.format(tld=tld, genre=genre)

                st.write(f"🔍 {query}")

                try:
                    results = ddgs.text(query, max_results=50)

                    found = 0

                    for r in results:
                        url = r.get("href")

                        if not url:
                            continue

                        if not is_blocked(url):
                            urls.add(url)
                            found += 1

                    st.write(f"→ {found} results")

                except Exception as e:
                    st.warning(f"Search failed (DDG block likely)")

                time.sleep(random.uniform(1.5, 3))

    st.info(f"Collected before filtering: {len(urls)}")

    new_urls = [u for u in urls if u not in existing_urls]

    # fallback if DDG blocks or DB too full
    if not new_urls:
        st.warning("⚠️ Using fallback (DDG likely blocked or duplicates)")
        return list(urls)[:30]

    return new_urls

# ==============================
# AUDIT (RELAXED)
# ==============================

def audit_site(url):

    data = {
        "url": url,
        "email": "",
        "pitch_score": 0
    }

    try:
        if not url.startswith("http"):
            url = "http://" + url

        if not url.startswith("https"):
            data["pitch_score"] += 2

        response = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text().lower()

        data["email"] = extract_email(response.text)

        if not soup.find("meta", {"name": "viewport"}):
            data["pitch_score"] += 2

        if re.search(r"©\s*(200\d|201[0-6])", text):
            data["pitch_score"] += 2

        if data["pitch_score"] < 1:
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
        st.warning("Enter genre and country")
        st.stop()

    init_db()
    existing_urls = get_existing_urls()

    urls = get_dorked_urls(genre, countries, existing_urls)

    st.success(f"Websites to analyze: {len(urls)}")

    save_urls(urls)

    leads = []
    progress = st.progress(0)

    for i, url in enumerate(urls):
        report = audit_site(url)

        if report:
            leads.append(report)

        progress.progress((i + 1) / len(urls))

    if leads:
        df = pd.DataFrame(leads).sort_values("pitch_score", ascending=False)

        st.success(f"✅ Found {len(leads)} leads")
        st.dataframe(df, use_container_width=True)

        st.download_button(
            "📥 Download CSV",
            df.to_csv(index=False).encode(),
            "leads.csv"
        )

    else:
        st.error("❌ No leads passed audit (try another niche)")
