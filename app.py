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
# SUPABASE (FIXED WITH YOUR VALUES)
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

def is_new_domain(domain):
    try:
        res = supabase.table("leads").select("domain").eq("domain", domain).execute()
        return len(res.data) == 0
    except:
        return False

def save_lead(data, search_term):
    try:
        supabase.table("leads").insert({
            "domain": get_domain(data["url"]),
            "url": data["url"],
            "email": data["email"],
            "pitch_score": data["pitch_score"],
            "search_term": search_term,
            "shown": False
        }).execute()
    except:
        pass

def get_unshown_leads(search_term):
    try:
        res = supabase.table("leads") \
            .select("*") \
            .eq("search_term", search_term) \
            .eq("shown", False) \
            .order("pitch_score", desc=True) \
            .execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

def mark_as_shown(domains):
    for d in domains:
        try:
            supabase.table("leads").update({"shown": True}).eq("domain", d).execute()
        except:
            pass

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

                except:
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

    st.info("Scanning...")

    urls = get_dorked_urls()

    unique_domains = set(get_domain(u) for u in urls if get_domain(u))
    st.info(f"🔍 Collected {len(unique_domains)} websites")

    new_count = 0

    for url in urls:
        report = audit_site(url)

        if report:
            domain = get_domain(report["url"])

            if not domain:
                continue

            if is_new_domain(domain):
                save_lead(report, genre)
                new_count += 1

    st.success(f"🆕 New Leads Added: {new_count}")

    st.subheader("🆕 Fresh Leads (Never Seen Before)")

    df_new = get_unshown_leads(genre)

    if not df_new.empty:
        st.dataframe(df_new)
        mark_as_shown(df_new["domain"].tolist())
    else:
        st.warning("No new leads found (all already seen)")
