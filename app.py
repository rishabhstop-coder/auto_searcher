import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
from ddgs import DDGS

st.set_page_config(layout="wide")
st.title("🔥 Website Revamp Lead Finder")

# ==============================
# USER INPUT (STREAMLIT)
# ==============================

genre = st.text_input("Enter business genre", "dental")

countries = st.multiselect(
    "Select countries",
    ["US", "CA", "EU", "UK", "AU"],
    default=["US"]
)

start = st.button("🚀 Start Scanning")

# ==============================
# CONFIG (UNCHANGED)
# ==============================

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
    'site:{tld} "{genre}" "contact"',
    'site:{tld} "{genre}" "call us"',
    'site:{tld} "{genre}" "about us"',
    'site:{tld} "{genre}" "services"',
    'site:{tld} "{genre}" "our team"',
    'site:{tld} "{genre}" "family owned"',
    'site:{tld} "{genre}" "serving since"',
    'site:{tld} "{genre}" "established"',
]

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}"

# ==============================
# FUNCTIONS (UNCHANGED LOGIC)
# ==============================

def is_blocked(url):
    domain = urlparse(url).netloc.lower()
    for bad in BLOCKED_DOMAINS:
        if bad in domain:
            return True
    return False


def extract_email(text):
    emails = re.findall(EMAIL_REGEX, text)
    return emails[0] if emails else ""


def get_dorked_urls():
    urls = set()
    random.shuffle(DORKS)

    with DDGS() as ddgs:
        for country in countries:
            tld = country_tlds.get(country.strip(), ".com")

            for dork in DORKS:
                query = dork.format(tld=tld, genre=genre)

                try:
                    results = ddgs.text(query, max_results=30)

                    for r in results:
                        url = r["href"]
                        if not is_blocked(url):
                            urls.add(url)

                except:
                    pass

                time.sleep(random.uniform(1, 2))

    return list(urls)


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
            timeout=8,
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
# MAIN EXECUTION
# ==============================

if start:

    st.info("Scanning... takes time. Don't panic.")

    urls = get_dorked_urls()

    st.write(f"🔍 Collected {len(urls)} websites")

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

        st.success(f"✅ Found {len(leads)} leads")

        st.dataframe(df)

        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "📥 Download CSV",
            csv,
            "revamp_leads.csv",
            "text/csv"
        )

    else:
        st.warning("No strong leads found.")
