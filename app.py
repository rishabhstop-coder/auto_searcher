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

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

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
    return urlparse(url).netloc.lower().replace("www.", "")

def is_blocked(url):
    domain = get_domain(url)
    return any(bad in domain for bad in BLOCKED_DOMAINS)

def extract_email(text):
    emails = re.findall(EMAIL_REGEX, text)
    return emails[0] if emails else ""

# ==============================
# SUPABASE FUNCTIONS
# ==============================

def is_new_lead(domain):
    res = supabase.table("leads").select("domain").eq("domain", domain).execute()
    return len(res.data) == 0

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
        print(e)
        return False

def get_all_leads():
    res = supabase.table("leads").select("*").order("pitch_score", desc=True).execute()
    return pd.DataFrame(res.data)

# ==============================
# SEARCH FUNCTION
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
                        url = r["href"]

                        if not is_blocked(url):
                            urls.add(url)

                except:
                    pass

                time.sleep(random.uniform(1, 2))

    return list(urls)

# ==============================
# AUDIT FUNCTION
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
# MAIN EXECUTION
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

            if is_new_lead(domain):
                if save_lead(report):
                    new_leads.append(report)

        progress.progress((i + 1) / len(urls))

    # ==============================
    # SHOW RESULTS
    # ==============================

    st.success(f"🆕 New Leads Found: {len(new_leads)}")

    if new_leads:
        st.subheader("🆕 New Leads")
        st.dataframe(pd.DataFrame(new_leads))

    # ALL STORED LEADS
    df_all = get_all_leads()

    if not df_all.empty:
        st.subheader("📊 All Leads (Persistent DB)")
        st.dataframe(df_all)
