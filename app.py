import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
from ddgs import DDGS
from supabase import create_client

st.set_page_config(layout="wide")
st.title("🔥 Website Revamp Lead Finder")

# ==============================
# SUPABASE CONNECTION
# ==============================

SUPABASE_URL = "https://cdtysrgzgfrzwlkeacax.supabase.co"
SUPABASE_KEY = "sb_publishable_BZ-OHKKeOdI3qOiz6MfvqQ_40EZOVlG"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==============================
# USER INPUT
# ==============================

genre = st.text_input("Enter business genre", "dental")

countries = st.multiselect(
    "Select countries",
    ["US", "CA", "EU", "UK", "AU"],
    default=["US"]
)

start = st.button("🚀 Start Scanning")

# ==============================
# CONFIG
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
# HELPERS
# ==============================

def get_domain(url):
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        return domain.strip()
    except:
        return None


def is_valid_url(url):
    return url and url.startswith("http")


def is_blocked(url):
    domain = get_domain(url)
    if not domain:
        return True
    return any(bad in domain for bad in BLOCKED_DOMAINS)


def extract_email(text):
    emails = re.findall(EMAIL_REGEX, text)
    return emails[0] if emails else ""


# ==============================
# SUPABASE FUNCTIONS
# ==============================

def is_new_lead(domain):
    try:
        res = supabase.table("leads").select("domain").eq("domain", domain).execute()
        return len(res.data) == 0
    except Exception as e:
        st.error(f"DB check error: {e}")
        return False


def save_lead(data):
    try:
        supabase.table("leads").insert({
            "domain": get_domain(data["url"]),
            "url": data["url"],
            "email": data["email"],
            "pitch_score": data["pitch_score"]
        }).execute()
        return True
    except Exception as e:
        st.error(f"Insert error: {e}")
        return False


def get_all_leads():
    try:
        res = supabase.table("leads").select("*").order("pitch_score", desc=True).execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Fetch error: {e}")
        return pd.DataFrame()


# ==============================
# SEARCH
# ==============================

def get_dorked_urls():
    urls = set()
    random.shuffle(DORKS)

    with DDGS() as ddgs:
        for country in countries:
            tld = country_tlds.get(country.strip(), ".com")

            for dork in DORKS:
                query = dork.format(tld=tld, genre=genre)

                try:
                    results = ddgs.text(query, max_results=25)

                    for r in results:
                        url = r.get("href")

                        if not is_valid_url(url):
                            continue

                        if is_blocked(url):
                            continue

                        urls.add(url)

                except Exception as e:
                    st.warning(f"Search error: {e}")

                time.sleep(1)

    return list(urls)


# ==============================
# AUDIT
# ==============================

def audit_site(url):
    try:
        if not url.startswith("http"):
            url = "http://" + url

        data = {
            "url": url,
            "email": "",
            "pitch_score": 0
        }

        if not url.startswith("https"):
            data["pitch_score"] += 3

        response = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text().lower()

        data["email"] = extract_email(response.text)

        if not soup.find("meta", attrs={"name": "viewport"}):
            data["pitch_score"] += 4

        if re.search(r"©\s*(200\d|201[0-6])", text):
            data["pitch_score"] += 2

        if data["pitch_score"] < 3:
            return None

        return data

    except:
        return None


# ==============================
# MAIN
# ==============================

if start:

    st.info("Scanning... takes time. Don't panic.")

    urls = get_dorked_urls()
    st.write(f"🔍 Collected {len(urls)} websites")

    new_leads = []
    progress = st.progress(0)

    for i, url in enumerate(urls):

        report = audit_site(url)

        if report:
            domain = get_domain(report["url"])

            if not domain:
                continue

            try:
                if is_new_lead(domain):
                    if save_lead(report):
                        new_leads.append(report)
            except Exception as e:
                st.error(f"Processing error: {e}")

        progress.progress((i + 1) / len(urls))

    # ==============================
    # DISPLAY
    # ==============================

    st.success(f"🆕 New Leads Found: {len(new_leads)}")

    if new_leads:
        st.subheader("🆕 New Leads")
        st.dataframe(pd.DataFrame(new_leads))

    df_all = get_all_leads()

    if not df_all.empty:
        st.subheader("📊 All Leads (Persistent DB)")
        st.dataframe(df_all)
