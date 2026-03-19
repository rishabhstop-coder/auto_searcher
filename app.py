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
# SUPABASE
# ==============================

SUPABASE_URL = "https://cdtysrgzgfrzwlkeacax.supabase.co"
SUPABASE_KEY = "sb_publishable_BZ-OHKKeOdI3qOiz6MfvqQ_40EZOVlG"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==============================
# INPUT
# ==============================

genre = st.text_input("Enter business genre", "dental")

countries = st.multiselect(
    "Select countries",
    ["US","CA","EU","UK","AU"],
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
        return urlparse(url).netloc.lower().replace("www.", "")
    except:
        return None

def is_blocked(url):
    domain = get_domain(url)
    if not domain:
        return True
    return any(b in domain for b in BLOCKED_DOMAINS)

def extract_email(text):
    emails = re.findall(EMAIL_REGEX, text)
    return emails[0] if emails else ""

# ==============================
# SUPABASE FUNCTIONS
# ==============================

def mark_previous_as_shown(search_term):
    try:
        supabase.table("leads") \
            .update({"shown": True}) \
            .eq("search_term", search_term) \
            .eq("shown", False) \
            .execute()
    except Exception as e:
        st.error(f"Mark error: {e}")


def is_new_domain(domain):
    try:
        res = supabase.table("leads") \
            .select("domain") \
            .eq("domain", domain) \
            .execute()
        return len(res.data) == 0
    except Exception as e:
        st.error(f"Check error: {e}")
        return False


def save_lead(data, search_term):
    try:
        supabase.table("leads").upsert({
            "domain": get_domain(data["url"]),
            "url": data["url"],
            "email": data["email"],
            "pitch_score": data["pitch_score"],
            "search_term": search_term,
            "shown": False
        }).execute()
    except Exception as e:
        st.error(f"Save failed: {e}")


def get_unshown_leads(search_term):
    try:
        res = supabase.table("leads") \
            .select("*") \
            .eq("search_term", search_term) \
            .eq("shown", False) \
            .execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Fetch new error: {e}")
        return pd.DataFrame()


def get_old_leads(search_term):
    try:
        res = supabase.table("leads") \
            .select("*") \
            .eq("search_term", search_term) \
            .eq("shown", True) \
            .execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Fetch old error: {e}")
        return pd.DataFrame()

# ==============================
# SEARCH (UNCHANGED)
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
                    results = ddgs.text(query, max_results=30)

                    for r in results:
                        url = r["href"]
                        if not is_blocked(url):
                            urls.add(url)

                except Exception:
                    pass

                time.sleep(random.uniform(1, 2))

    return list(urls)

# ==============================
# AUDIT
# ==============================

def audit_site(url):
    try:
        if not url.startswith("http"):
            url = "http://" + url

        data = {"url": url, "email": "", "pitch_score": 0}

        if not url.startswith("https"):
            data["pitch_score"] += 3

        response = requests.get(url, timeout=8)
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

    # Step 1: Mark previous leads as old
    mark_previous_as_shown(genre)

    st.info("Scanning...")

    urls = list(set(get_dorked_urls()))

    unique_domains = set(get_domain(u) for u in urls if get_domain(u))
    st.info(f"🔍 Collected {len(unique_domains)} websites")

    # ==============================
    # SHOW COLLECTED
    # ==============================

    st.subheader("🌐 Collected Websites")

    df_urls = pd.DataFrame({
        "url": urls,
        "domain": [get_domain(u) for u in urls]
    })

    st.dataframe(df_urls)

    # ==============================
    # PROCESS
    # ==============================

    new_count = 0

    for url in urls:
        report = audit_site(url)

        if report:
            domain = get_domain(report["url"])

            if domain and is_new_domain(domain):
                save_lead(report, genre)
                new_count += 1

    st.success(f"🆕 New Leads Added: {new_count}")

    # ==============================
    # SHOW FRESH
    # ==============================

    st.subheader("🆕 Fresh Leads (This Run)")

    df_new = get_unshown_leads(genre)

    if not df_new.empty:
        st.dataframe(df_new)
    else:
        st.warning("No new leads found")

    # ==============================
    # SHOW OLD
    # ==============================

    st.subheader("📂 Previously Found Leads")

    df_old = get_old_leads(genre)

    if not df_old.empty:
        st.dataframe(df_old)
    else:
        st.info("No old leads yet")

    # ==============================
    # DEBUG (optional but useful)
    # ==============================

    st.subheader("🔍 Debug DB Data")
    try:
        debug = supabase.table("leads").select("*").execute()
        st.write(debug.data)
    except Exception as e:
        st.error(e)
