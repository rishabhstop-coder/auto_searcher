import requests
from bs4 import BeautifulSoup
import re
import time
import random
import pandas as pd
from urllib.parse import urlparse
import sqlite3

# FIXED IMPORT (THIS WAS YOUR MAIN PROBLEM)
try:
    from duckduckgo_search import DDGS
except:
    from ddgs import DDGS


# ==============================
# USER INPUT
# ==============================

genre = input("Enter business genre (dental, law, real estate): ").strip()

countries = input(
    "Enter countries (US, CA, EU, UK, AU): "
).upper().split(",")

countries = [c.strip() for c in countries if c.strip()]


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
# COUNTRY TLD MAP
# ==============================

country_tlds = {
    "US": ".us",
    "CA": ".ca",
    "EU": ".eu",
    "UK": ".co.uk",
    "AU": ".com.au"
}


# ==============================
# BLOCKED DOMAINS
# ==============================

BLOCKED_DOMAINS = [
    "facebook","linkedin","instagram","youtube","twitter","x",
    "wikipedia","amazon","zillow","realtor","yelp","indeed",
    "glassdoor","tripadvisor","pinterest","github",
    "google","bing","apple","microsoft","reddit",
    "yellowpages","mapquest","bbb","angi","houzz","manta"
]


# ==============================
# SEARCH DORKS
# ==============================

DORKS = [
    'site:{tld} "{genre}" contact',
    'site:{tld} "{genre}" "contact us"',
    'site:{tld} "{genre}" "call us"',
    'site:{tld} "{genre}" "about us"',
    'site:{tld} "{genre}" services',
    'site:{tld} "{genre}" "our team"',
    '"{genre}" "contact us" site:{tld}',
]


# ==============================
# EMAIL REGEX
# ==============================

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}"


# ==============================
# FILTER
# ==============================

def is_blocked(url):
    domain = urlparse(url).netloc.lower()
    return any(b in domain for b in BLOCKED_DOMAINS)


# ==============================
# SEARCH FUNCTION
# ==============================

def get_dorked_urls(existing_urls):

    urls = set()
    random.shuffle(DORKS)

    with DDGS() as ddgs:

        for country in countries:

            tld = country_tlds.get(country, ".com")

            for dork in DORKS:

                query = dork.format(tld=tld, genre=genre)

                print("\nSearching:", query)

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

                except Exception as e:
                    print("Search error:", e)

                time.sleep(random.uniform(1.0, 2.0))

    return list(urls)


# ==============================
# EMAIL EXTRACTION
# ==============================

def extract_email(text):
    emails = re.findall(EMAIL_REGEX, text)
    return emails[0] if emails else ""


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
            headers={"User-Agent":"Mozilla/5.0"}
        )

        load_time = time.time() - start
        data["load_time"] = round(load_time,2)

        if load_time > 4:
            data["speed_issue"] = True
            data["pitch_score"] += 2

        soup = BeautifulSoup(response.text,"html.parser")
        text = soup.get_text().lower()

        data["email"] = extract_email(response.text)

        if not soup.find("meta",attrs={"name":"viewport"}):
            data["mobile_issue"] = True
            data["pitch_score"] += 4

        tables = soup.find_all("table")
        divs = soup.find_all("div")

        if len(tables) > 5 and len(divs) < 20:
            data["tech_stack"] = "Table Layout"
            data["pitch_score"] += 2

        if re.search(r"©\s*(200\d|201[0-6])",text):
            data["outdated_site"] = True
            data["pitch_score"] += 2

        if ".swf" in text:
            data["tech_stack"] = "Flash"
            data["pitch_score"] += 5

        if data["pitch_score"] < 3:
            return None

        return data

    except Exception as e:
        print("Audit failed:", url)
        return None


# ==============================
# MAIN
# ==============================

print("\nSearching for outdated websites...\n")

init_db()
existing_urls = get_existing_urls()

urls = get_dorked_urls(existing_urls)

print(f"\nCollected {len(urls)} NEW websites\n")

save_urls(urls)

leads = []

for url in urls:

    print("\n==============================")
    print("Analyzing:",url)

    report = audit_site(url)

    if report:
        print("Score:",report["pitch_score"])
        print("Email:",report["email"])
        leads.append(report)
    else:
        print("Skipped")


# ==============================
# SAVE CSV
# ==============================

if leads:
    df = pd.DataFrame(leads)
    df = df.sort_values(by="pitch_score",ascending=False)
    df.to_csv("revamp_leads.csv",index=False)
    print("\nSaved",len(leads),"leads")

else:
    print("\nNo strong leads found.")
