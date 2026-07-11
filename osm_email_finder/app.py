import os
import re
import time
import threading
import requests
from urllib.parse import urljoin, urlparse
from flask import Flask, render_template, request, jsonify, send_file
from openpyxl import Workbook

app = Flask(__name__)

HEADERS = {"User-Agent": "TugdiEmailFinder/1.0 (kisisel kullanim - lutfen degistirin)"}

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

KEYWORD_TAG_MAP = {
    "auto": ["shop=car_repair", "shop=car", "shop=car_parts", "shop=tyres"],
    "oto": ["shop=car_repair", "shop=car", "shop=car_parts", "shop=tyres"],
    "restaurant": ["amenity=restaurant"],
    "restoran": ["amenity=restaurant"],
    "dentist": ["amenity=dentist"],
    "dis": ["amenity=dentist"],
    "lawyer": ["office=lawyer"],
    "avukat": ["office=lawyer"],
    "plumber": ["craft=plumber"],
    "tesisatci": ["craft=plumber"],
    "electrician": ["craft=electrician"],
    "elektrikci": ["craft=electrician"],
    "real estate": ["office=estate_agent"],
    "emlak": ["office=estate_agent"],
    "hotel": ["tourism=hotel"],
    "otel": ["tourism=hotel"],
    "gym": ["leisure=fitness_centre"],
    "spor salonu": ["leisure=fitness_centre"],
    "dry cleaning": ["shop=dry_cleaning"],
    "kuru temizleme": ["shop=dry_cleaning"],
    "bakery": ["shop=bakery"],
    "firin": ["shop=bakery"],
    "hair": ["shop=hairdresser"],
    "kuafor": ["shop=hairdresser"],
    "insurance": ["office=insurance"],
    "sigorta": ["office=insurance"],
    "accountant": ["office=accountant"],
    "muhasebe": ["office=accountant"],
}

BAD_EMAIL_DOMAINS = {
    "wixpress.com", "sentry.io", "example.com", "godaddy.com",
    "schema.org", "w3.org", "yourdomain.com", "domain.com",
    "email.com", "test.com", "sentry-next.wixpress.com",
    "domainsbyproxy.com", "wordpress.com",
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

progress_state = {
    "total": 0,
    "processed": 0,
    "emails_found": 0,
    "status": "idle",
    "error": None,
    "results": [],
    "file_path": None,
    "keyword": None,
    "started_at": 0,
}
lock = threading.Lock()

NY_BBOX = "40.4,-79.9,45.1,-71.7"


def _run_overpass(query):
    last_err = None
    for url in OVERPASS_URLS:
        try:
            r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=(15, 110))
            r.raise_for_status()
            data = r.json()
            if not data.get("elements") and data.get("remark"):
                last_err = data["remark"]
                continue
            return data.get("elements", [])
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Overpass API'ye erişilemedi veya zaman aşımına uğradı: {last_err}")


def overpass_query(keyword):
    kw = keyword.lower().strip()
    tags = KEYWORD_TAG_MAP.get(kw, [])
    safe_kw = re.sub(r'["\\]', "", keyword)

    elements = []

    if tags:
        tag_filters = "".join(
            f'nwr[{t.split("=")[0]}="{t.split("=")[1]}"]({NY_BBOX});' for t in tags
        )
        q1 = f"[out:json][timeout:90];({tag_filters});out center tags 300;"
        try:
            elements += _run_overpass(q1)
        except Exception:
            pass

    if not elements:
        name_filter = (
            f'nwr["shop"]["name"~"{safe_kw}",i]({NY_BBOX});'
            f'nwr["office"]["name"~"{safe_kw}",i]({NY_BBOX});'
            f'nwr["amenity"]["name"~"{safe_kw}",i]({NY_BBOX});'
            f'nwr["craft"]["name"~"{safe_kw}",i]({NY_BBOX});'
        )
        q2 = f"[out:json][timeout:90];({name_filter});out center tags 300;"
        elements += _run_overpass(q2)

    return elements


def extract_emails_from_text(text):
    found = set()
    for m in EMAIL_RE.findall(text):
        domain = m.split("@")[-1].lower()
        if domain in BAD_EMAIL_DOMAINS:
            continue
        if m.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")):
            continue
        found.add(m)
    return found


def find_emails_on_site(base_url, timeout=8):
    emails = set()
    if not base_url:
        return emails
    if not base_url.startswith("http"):
        base_url = "http://" + base_url
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    paths = ["", "contact", "contact-us", "about", "about-us", "iletisim"]
    for p in paths:
        url = urljoin(root + "/", p)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                emails |= extract_emails_from_text(resp.text)
                if emails:
                    break
        except requests.RequestException:
            continue
        time.sleep(0.3)
    return emails


def short_address(tags):
    parts = []
    for k in ["addr:housenumber", "addr:street", "addr:city", "addr:state", "addr:postcode"]:
        if tags.get(k):
            parts.append(tags[k])
    return ", ".join(parts) if parts else ""


def process_search(keyword):
    with lock:
        progress_state.update(
            total=0, processed=0, emails_found=0, status="searching",
            error=None, results=[], file_path=None, keyword=keyword,
            started_at=time.time(),
        )

    try:
        elements = overpass_query(keyword)
    except Exception as e:
        with lock:
            progress_state["status"] = "error"
            progress_state["error"] = str(e)
        return

    seen = set()
    unique = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        key = (name.lower(), tags.get("addr:street", "").lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(el)

    with lock:
        progress_state["total"] = len(unique)
        progress_state["status"] = "processing"

    results = []
    for el in unique:
        tags = el.get("tags", {})
        name = tags.get("name", "")
        phone = tags.get("contact:phone") or tags.get("phone", "")
        website = tags.get("contact:website") or tags.get("website", "")
        email = tags.get("contact:email") or tags.get("email", "")
        address = short_address(tags)

        if not email and website:
            try:
                found = find_emails_on_site(website)
                if found:
                    email = sorted(found)[0]
            except Exception:
                pass

        with lock:
            progress_state["processed"] += 1

        if email:
            results.append({
                "Firma Adı": name or "Bulunamadı",
                "Adres": address or "Bulunamadı",
                "Telefon": phone or "Bulunamadı",
                "Email": email,
            })
            with lock:
                progress_state["emails_found"] += 1
                progress_state["results"] = list(results)

    wb = Workbook()
    ws = wb.active
    ws.title = "Sonuçlar"
    ws.append(["Firma Adı", "Adres", "Telefon", "Email"])
    for row in results:
        ws.append([row["Firma Adı"], row["Adres"], row["Telefon"], row["Email"]])
    out_path = os.path.join(os.getcwd(), "sonuclar.xlsx")
    wb.save(out_path)

    with lock:
        progress_state["status"] = "done"
        progress_state["file_path"] = out_path


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
    data = request.get_json(force=True)
    keyword = (data.get("keyword") or "").strip()
    if not keyword:
        return jsonify({"error": "Anahtar kelime gerekli"}), 400
    with lock:
        stuck = (
            progress_state["status"] in ("searching", "processing")
            and (time.time() - progress_state["started_at"]) > 260
        )
        if progress_state["status"] in ("searching", "processing") and not stuck:
            return
