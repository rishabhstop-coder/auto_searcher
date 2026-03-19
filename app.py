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
    "facebook","linkedin","instagram","youtube","google"
]

DORKS = [
    'site:{tld} "{genre}" "contact"',
    'site:{tld} "{genre}" "about us"',
    'site:{tld} "{genre}" "services"',
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

def is_valid(url):
    return url and url.startswith("http")

def extract_email(text):
    emails = re.findall(EMAIL_REGEX, text)
    return emails[0] if emails else ""

# ==============================
# DB FUNCTIONS
# ==============================

def save_search(genre):
    try:
        supabase.table("search_history").insert({
            "search_term": genre
        }).execute()
    except:
        pass

def is_new_lead(domain):
    res = supabase.table("leads").select("domain").eq("domain", domain).execute()
    return len(res.data) == 0

def save_lead(data):
    try:
        supabase.table("leads").insert({
            "domain": get_domain(data["url"]),
            "url": data["url"],
            "email": data["email"],
            "pitch_score": data["pitch_score"],
            "clicked": False
        }).execute()
        return True
    except:
        return False

def mark_clicked(domain):
    supabase.table("leads").update({"clicked": True}).eq("domain", domain).execute()

def get_all_leads():
    res = supabase.table("leads").select("*").order("pitch_score", desc=True).execute()
    return pd.DataFrame(res.data)

# ==============================
# SEARCH
# ==============================

def get_urls():
    urls = set()

    with DDGS() as ddgs:
        for country in countries:
            tld = country_tlds.get(country, ".com")

            for dork in DORKS:
                query = dork.format(tld=tld, genre=genre)

                try:
                    results = ddgs.text(query, max_results=20)

                    for r in results:
                        url = r.get("href")

                        if not is_valid(url):
                            continue

                        urls.add(url)

                except:
                    pass

                time.sleep(1)

    return list(urls)

# ==============================
# AUDIT
# ==============================

def audit(url):
    try:
        data = {
            "url": url,
            "email": "",
            "pitch_score": 0
        }

        if not url.startswith("https"):
            data["pitch_score"] += 3

        res = requests.get(url, timeout=6)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text().lower()

        data["email"] = extract_email(res.text)

        if not soup.find("meta", attrs={"name": "viewport"}):
            data["pitch_score"] += 4

        if "2010" in text or "2012" in text:
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

    save_search(genre)

    st.info("Scanning...")

    urls = get_urls()

    unique_domains = set(get_domain(u) for u in urls if get_domain(u))
    st.info(f"🔍 Collected {len(unique_domains)} unique websites")

    new_leads = []
    progress = st.progress(0)

    for i, url in enumerate(urls):

        report = audit(url)

        if report:
            domain = get_domain(report["url"])

            if not domain:
                continue

            if is_new_lead(domain):
                if save_lead(report):
                    new_leads.append(report)

        progress.progress((i + 1) / len(urls))

    st.success(f"🆕 New Leads Found: {len(new_leads)}")

# ==============================
# DISPLAY ALL LEADS
# ==============================

df = get_all_leads()

if not df.empty:

    st.subheader("📊 All Leads")

    for i, row in df.iterrows():

        col1, col2, col3 = st.columns([4,2,2])

        with col1:
            st.write(row["url"])

        with col2:
            st.write("📧", row["email"] if row["email"] else "-")

        with col3:
            if row.get("clicked"):
                st.success("Clicked ✅")
            else:
                if st.button(f"Open {i}"):
                    mark_clicked(row["domain"])
                    st.rerun()
