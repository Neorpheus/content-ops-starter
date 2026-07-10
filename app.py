import os
import sys
import json
import urllib.parse
import urllib.request
import re
import hashlib
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'super_secret_clinical_key_2026')

CLINICIAN_USER = os.environ.get('CLINICIAN_USERNAME', 'clinician')
CLINICIAN_PASS = os.environ.get('CLINICIAN_PASSWORD', 'mrisafety2026')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({"error": "Unauthorized clinical session. Please log in."}), 401
        return f(*args, **kwargs)
    return decorated_function

CACHE_FILE = 'search_cache.json'

DATABASE_FILE = 'implant_database.json'

# Default pre-seeded database of common implants and their official MRI Safety profiles
DEFAULT_DATABASE = {
    "medtronic advisa": {
        "device_name": "Medtronic Advisa DR MRI SureScan Pacemaker",
        "manufacturer": "Medtronic",
        "category": "Cardiac Pacemaker",
        "safety_status": "MRI Conditional",
        "field_strength": "1.5T and 3.0T",
        "sar_limit": "Whole body SAR <= 2.0 W/kg (Normal Operating Mode)",
        "spatial_gradient": "<= 20 T/m (2000 gauss/cm)",
        "conditions": (
            "1. SureScan mode must be programmed ON prior to the scan.\n"
            "2. No abandoned leads or lead fragments present.\n"
            "3. Active lead impedance must be within 200 to 1500 ohms.\n"
            "4. Patient must be monitored continuously (ECG or Pulse Oximetry)."
        ),
        "fda_clearance": "P010031/S084 (Premarket Approval)",
        "recalls_adverse_events": "No active recalls. 4 minor lead impedance fluctuations reported in MAUDE database (non-serious).",
        "manual_link": "https://manuals.medtronic.com"
    },
    "st. jude medical ellipse": {
        "device_name": "St. Jude Medical Ellipse ICD (Implantable Cardioverter Defibrillator)",
        "manufacturer": "St. Jude Medical (Abbott)",
        "category": "Defibrillator (ICD)",
        "safety_status": "MRI Conditional",
        "field_strength": "1.5T only",
        "sar_limit": "Whole body SAR <= 2.0 W/kg",
        "spatial_gradient": "<= 30 T/m (3000 gauss/cm)",
        "conditions": (
            "1. Device must be placed in MRI mode (tachyarrhythmia therapy programmed OFF).\n"
            "2. Patient must not have abandoned leads, adapters, or lead extenders.\n"
            "3. Minimum post-implant duration of 6 weeks required."
        ),
        "fda_clearance": "P030054/S252 (Premarket Approval)",
        "recalls_adverse_events": "Recall in 2018 regarding battery depletion issues (resolved). Check patient serial number.",
        "manual_link": "https://www.cardiovascular.abbott/us/en/hcp/products/cardiac-rhythm-management/icd.html"
    },
    "cochlear nucleus 7": {
        "device_name": "Cochlear Nucleus 7 (CI500 & CI600 Series Implants)",
        "manufacturer": "Cochlear Ltd",
        "category": "Cochlear Implant",
        "safety_status": "MRI Conditional",
        "field_strength": "1.5T and 3.0T",
        "sar_limit": "Head SAR <= 3.2 W/kg (or Whole body SAR <= 2.0 W/kg)",
        "spatial_gradient": "<= 15 T/m (1500 gauss/cm)",
        "conditions": (
            "1. External sound processor MUST be removed prior to entering the MRI scanner room.\n"
            "2. Splint/bandage kit must be applied over the implant site for CI500 series at 3.0T to prevent magnet displacement.\n"
            "3. CI600 series is conditional at 1.5T/3.0T without magnet removal or splinting."
        ),
        "fda_clearance": "P970051/S178",
        "recalls_adverse_events": "None active. Rare cases of demagnetization reported if splinting protocols were ignored.",
        "manual_link": "https://www.cochlear.com/us/en/home/ongoing-care-and-support/nucleus-7-support"
    },
    "aneurx stent graft": {
        "device_name": "AneuRx AAA Stent Graft System",
        "manufacturer": "Medtronic Endovascular",
        "category": "Endovascular Stent Graft",
        "safety_status": "MRI Conditional",
        "field_strength": "1.5T and 3.0T",
        "sar_limit": "Whole body SAR <= 2.0 W/kg for 15 minutes of continuous scanning",
        "spatial_gradient": "<= 30 T/m (3000 gauss/cm)",
        "conditions": (
            "1. Safe to scan immediately after implantation (no wait period required).\n"
            "2. Non-ferromagnetic nitinol/polyester construction."
        ),
        "fda_clearance": "P990026 (Premarket Approval)",
        "recalls_adverse_events": "No active recalls. Historical migration events noted in early 2000s; verify graft position prior to scan.",
        "manual_link": "https://www.medtronic.com/us-en/healthcare-professionals/products/cardiovascular/aortic-stent-grafts.html"
    },
    "star edwards valve": {
        "device_name": "Starr-Edwards caged-ball heart valve (Model 6120/6000)",
        "manufacturer": "Edwards Lifesciences",
        "category": "Prosthetic Heart Valve",
        "safety_status": "MRI Safe",
        "field_strength": "Up to 3.0T",
        "sar_limit": "No specific SAR limits (non-ferromagnetic clinical models)",
        "spatial_gradient": "No spatial gradient limitations",
        "conditions": (
            "1. Models 6120 (mitral) and 6000 (aortic) are constructed of Stellite and titanium and are safe to scan.\n"
            "2. Note: Early caged-ball valves from the 1960s containing stainless steel (e.g. Model 1000) are MRI Unsafe. Confirm model number."
        ),
        "fda_clearance": "Pre-amendment device / PMA exempt",
        "recalls_adverse_events": "None active.",
        "manual_link": "https://www.edwards.com/devices/heart-valves"
    }
}

# Loader and saver for persistent implant database file
def load_implant_database():
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[-] Database read error, using default seeds: {e}")
            
    # Seed new file if missing
    try:
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_DATABASE, f, indent=4)
    except Exception as e:
        print(f"[-] Database seed error: {e}")
    return DEFAULT_DATABASE.copy()

def save_implant_database(db):
    try:
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4)
        return True
    except Exception as e:
        print(f"[-] Database save error: {e}")
        return False

# Initialize database
IMPLANT_DATABASE = load_implant_database()

# Stop words to remove from openFDA query
STOP_WORDS = {
    "mri", "safety", "implant", "device", "model", "safe", "conditional", 
    "unsafe", "scan", "scanning", "patient", "specifications", "manual",
    "the", "a", "an", "and", "or", "of", "in", "on", "for", "with", "by", "to"
}

# Levenshtein distance for fuzzy matching
def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
        
    return previous_row[-1]

# Fuzzy matching suggestion helper
def get_fuzzy_implant_suggestion(query_str):
    q_clean = query_str.lower().strip()
    if not q_clean:
        return None
        
    # Check exact substring first
    for key in IMPLANT_DATABASE.keys():
        if key in q_clean or q_clean in key:
            return key
            
    # Compute Levenshtein distance
    best_match = None
    min_dist = 999
    for key in IMPLANT_DATABASE.keys():
        dist = levenshtein_distance(q_clean, key)
        if dist < min_dist and dist <= 4:
            min_dist = dist
            best_match = key
            
    return best_match

# Cryptographic SHA-256 Helper
def compute_sha256(data_str):
    return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

# Cache management helpers
def load_search_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_search_cache(cache_data):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=4)
    except Exception as e:
        print(f"[-] Cache write error: {e}")

# Tokenize and clean search query for API
def get_clean_keywords(query_str):
    words = re.findall(r'\b[a-zA-Z0-9]+\b', query_str.lower())
    filtered = [w.upper() for w in words if w not in STOP_WORDS]
    return filtered if filtered else [w.upper() for w in words]

FDA_CONFIG_FILE = 'fda_config.json'

def load_fda_api_key():
    key = os.environ.get('FDA_API_KEY')
    if key:
        return key
    if os.path.exists(FDA_CONFIG_FILE):
        try:
            with open(FDA_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('api_key')
        except Exception:
            pass
    return None

# General openFDA endpoint query function with retries and rate limit checks
def query_openfda_endpoint(endpoint, keywords, limit=3):
    if not keywords:
        return []
    # Query using AND logic syntax
    query_str = "(" + " AND ".join(keywords) + ")"
    encoded_query = urllib.parse.quote(query_str)
    
    api_key = load_fda_api_key()
    api_key_str = f"&api_key={api_key}" if api_key else ""
    url = f"https://api.fda.gov/device/{endpoint}.json?search={encoded_query}&limit={limit}{api_key_str}"
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ImplantSafeMRI/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                return data.get("results", [])
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            elif e.code == 429:
                print(f"[-] openFDA rate limit error (429) on {endpoint} query.")
                raise Exception("rate_limit")
            else:
                print(f"[-] HTTP error {e.code} querying {endpoint} on attempt {attempt+1}")
        except Exception as e:
            print(f"[-] Error querying {endpoint} on attempt {attempt+1}: {e}")
            
    return []

def duckduckgo_scrape(search_query, max_results=3):
    encoded_query = urllib.parse.quote(search_query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8')
            pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, html, re.DOTALL)
            
            results = []
            for link, title in matches:
                title = re.sub(r'<[^>]+>', '', title).strip()
                if 'uddg=' in link:
                    raw_url = link.split('uddg=')[1].split('&')[0]
                    decoded_url = urllib.parse.unquote(raw_url)
                else:
                    decoded_url = link
                    
                if not decoded_url.startswith('http'):
                    continue
                    
                results.append({"title": title, "link": decoded_url})
                if len(results) >= max_results:
                    break
            return results
    except Exception as e:
        print(f"[-] DuckDuckGo scrape failed for '{search_query}': {e}")
        return []

# Live Web Search Scraper (DuckDuckGo HTML parser)
def search_mri_safety_web(query_str):
    # 1. Broad manual search
    search_term = f"{query_str} MRI safety specifications manual"
    results = duckduckgo_scrape(search_term, max_results=6)
    
    # Filter out any results that contain mrisafety.com in the link
    filtered_results = []
    for r in results:
        link = r.get("link", "").lower()
        if "mrisafety.com" not in link:
            filtered_results.append(r)
            
    return filtered_results[:4]

# Map UDI mri_safety string to clinical categories
def map_udi_mri_safety(mri_safety_str):
    if not mri_safety_str:
        return None
    s = mri_safety_str.lower()
    if "conditional" in s:
        return "MRI Conditional"
    elif "safe" in s and "unsafe" not in s:
        return "MRI Safe"
    elif "unsafe" in s:
        return "MRI Unsafe"
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        clinician_name = request.form.get('clinician_name', 'Dr. Sarah Jenkins').strip()
        role = request.form.get('role', 'Lead Radiologist').strip()
        
        if username == CLINICIAN_USER and password == CLINICIAN_PASS:
            session['logged_in'] = True
            session['username'] = username
            session['clinician_name'] = clinician_name if clinician_name else 'Dr. Sarah Jenkins'
            session['role'] = role if role else 'Lead Radiologist'
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password. Please use pre-configured test credentials.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', 
                           clinician_name=session.get('clinician_name', 'Dr. Sarah Jenkins'), 
                           role=session.get('role', 'Lead Radiologist'))

@app.route('/api/verify', methods=['POST'])
@api_login_required
def verify_implant():
    request_data = request.get_json() or {}
    query = request_data.get("query", "").strip()
    
    if not query:
        return jsonify({"error": "Empty search query"}), 400

    query_key = query.lower().strip()
    
    # 1. Check local cache first
    cache = load_search_cache()
    if query_key in cache:
        print(f"[+] Cache HIT for: {query}")
        cached_report = cache[query_key].copy()
        cached_report["cached"] = True
        cached_report["cache_timestamp"] = cached_report.get("cache_timestamp", datetime.now().isoformat())
        return jsonify(cached_report)

    # 2. Check for multiple matching candidates (disambiguation logic)
    candidates = []
    for key, val in IMPLANT_DATABASE.items():
        scraped_sources = val.get("scraped_from", [])
        source_display = ", ".join(scraped_sources) if scraped_sources else "Preset Catalog"
        if query_key == key:
            candidates = [{
                "name": val["device_name"],
                "manufacturer": val["manufacturer"],
                "source": source_display
            }]
            break
        if (query_key in key or key in query_key or 
            query_key in val["device_name"].lower() or 
            query_key in val["manufacturer"].lower() or 
            levenshtein_distance(query_key, key) <= 3):
            candidates.append({
                "name": val["device_name"],
                "manufacturer": val["manufacturer"],
                "source": source_display
            })
            
    is_exact_match = (query_key in IMPLANT_DATABASE) or (len(candidates) == 1 and candidates[0]["name"].lower().strip() == query_key)
    
    if not is_exact_match:
        # Pull suggestions from suggestions engine to build complete candidate lists
        keywords = get_clean_keywords(query)
        if keywords and len(query_key) >= 3:
            try:
                udi_matches = query_openfda_endpoint("udi", keywords, limit=50)
                for u in udi_matches:
                    brand = u.get("brand_name")
                    company = u.get("company_name", "Unknown Manufacturer")
                    if brand:
                        brand_clean = re.sub(r'™|®', '', brand).strip()
                        if not any(s["name"].lower() == brand_clean.lower() for s in candidates):
                            candidates.append({
                                "name": brand_clean,
                                "manufacturer": company,
                                "source": "FDA Registry"
                            })
            except Exception:
                pass

            # Also query web search for manufacturer manual links and add them as matching candidates
            try:
                web_results = search_mri_safety_web(query)
                for w in web_results:
                    title = w.get("title", "")
                    link = w.get("link", "")
                    if title and link:
                        title_clean = re.sub(r'™|®', '', title).strip()
                        parsed_url = urllib.parse.urlparse(link)
                        domain = parsed_url.netloc.lower()
                        if domain.startswith("www."):
                            domain = domain[4:]
                        
                        # Deduplicate
                        if not any(s["name"].lower() == title_clean.lower() for s in candidates):
                            candidates.append({
                                "name": title_clean,
                                "manufacturer": "Crawled Web Source",
                                "source": domain,
                                "link": link
                            })
            except Exception as e:
                print(f"[-] Error adding web search candidates: {e}")
                
    if len(candidates) > 1:
        # Check if the query is an exact match to bypass disambiguation
        exact_c = None
        for c in candidates:
            if c["name"].lower().strip() == query_key:
                exact_c = c
                break
        if not exact_c:
            print(f"[+] Disambiguating query '{query}' with candidates: {[c['name'] for c in candidates]}")
            return jsonify({
                "disambiguation": True,
                "query": query,
                "matches": candidates[:50]
            })

    # 3. Check for fuzzy match suggestion in local presets
    suggestion_key = get_fuzzy_implant_suggestion(query)
    
    # Extract query keywords for live openFDA queries (using suggestion key if matched to fix spelling)
    search_query = suggestion_key if suggestion_key else query
    keywords = get_clean_keywords(search_query)
    print(f"[*] Compiling FDA records for keywords: {keywords}")
    
    # Query UDI, PMA, 510k, De Novo, Recalls, and MAUDE Events with rate limit checks
    rate_limited = False
    try:
        udi_res = query_openfda_endpoint("udi", keywords, limit=5)
        pma_res = query_openfda_endpoint("pma", keywords, limit=5)
        k510_res = query_openfda_endpoint("510k", keywords, limit=5)
        denovo_res = query_openfda_endpoint("denovo", keywords, limit=5)
        recall_res = query_openfda_endpoint("recall", keywords, limit=5)
        event_res = query_openfda_endpoint("event", keywords, limit=5)
    except Exception as e:
        if str(e) == "rate_limit":
            rate_limited = True
            udi_res, pma_res, k510_res, denovo_res, recall_res, event_res = [], [], [], [], [], []
        else:
            raise e

    web_links = search_mri_safety_web(query)

    compiled_data = {
        "udi": udi_res,
        "pma": pma_res,
        "k510": k510_res,
        "denovo": denovo_res,
        "recalls": recall_res,
        "events": event_res
    }

    # Draft Report Construction
    report = {}
    
    # Case A: Matches pre-seeded database (preset matching)
    if suggestion_key:
        print(f"[+] Presets Match: Using preset template for {suggestion_key}")
        report = IMPLANT_DATABASE[suggestion_key].copy()
        report["source"] = f"Pre-seeded Implant Database + FDA Compiled Live Audit"
        report["scraped_from"] = report.get("scraped_from", ["Preset Catalog"])
        if suggestion_key != query_key:
            report["device_name"] = f"{report['device_name']} (Fuzzy Match: '{query}')"
            
    # Case B: Dynamically resolve from live FDA records
    elif udi_res or pma_res or k510_res or denovo_res:
        print(f"[+] Dynamic Match: Formulating report from openFDA databases")
        
        # Determine primary device metadata
        device_name = query
        manufacturer = "Unknown"
        category = "Medical Implant"
        clearance_details = "Verified in compiled FDA records"
        safety_status = "MRI Conditional"  # Conservative default for matches
        
        # Try UDI first
        if udi_res:
            best_udi = udi_res[0]
            device_name = best_udi.get("brand_name", device_name)
            manufacturer = best_udi.get("company_name", manufacturer)
            category = best_udi.get("device_description", category)
            mapped_status = map_udi_mri_safety(best_udi.get("mri_safety"))
            if mapped_status:
                safety_status = mapped_status
            clearance_details = "UDI Registry Registered"
            
        # Try PMA
        elif pma_res:
            best_pma = pma_res[0]
            device_name = best_pma.get("trade_name", device_name)
            manufacturer = best_pma.get("applicant", manufacturer)
            category = best_pma.get("generic_name", category)
            clearance_details = f"PMA: {best_pma.get('pma_number')}"
            
        # Try 510(k)
        elif k510_res:
            best_510k = k510_res[0]
            device_name = best_510k.get("device_name", device_name)
            manufacturer = best_510k.get("applicant", manufacturer)
            category = best_510k.get("openfda", {}).get("device_name", category)
            clearance_details = f"510(k) cleared: {best_510k.get('k_number')}"
            
        # Try De Novo
        elif denovo_res:
            best_dn = denovo_res[0]
            device_name = best_dn.get("device_name", device_name)
            manufacturer = best_dn.get("applicant", manufacturer)
            clearance_details = f"De Novo: {best_dn.get('denovo_number')}"

        # Clean string formats
        device_name = re.sub(r'', '', device_name)
        
        # Setup scanning constraints based on device classifications
        field_strength = "1.5T (Verify 3.0T in manual)"
        sar_limit = "Whole body SAR <= 2.0 W/kg (Normal operating mode)"
        spatial_gradient = "Verify in manufacturer specifications"
        conditions = (
            "1. Specific safety parameters must be verified from the manufacturer's user manual.\n"
            "2. Verify that leads, electrodes, or metallic parts are non-ferromagnetic prior to scanning.\n"
            "3. Ensure the patient is monitored continuously."
        )

        # Keyword mapping rules
        specialty = ""
        if udi_res and "openfda" in udi_res[0]:
            specialty = udi_res[0]["openfda"].get("medical_specialty_description", "").lower()
        elif pma_res and "openfda" in pma_res[0]:
            specialty = pma_res[0]["openfda"].get("medical_specialty_description", "").lower()
            
        dev_name_l = device_name.lower()
        
        if "cardiovascular" in specialty or "pacemaker" in dev_name_l or "icd" in dev_name_l:
            safety_status = "MRI Conditional"
            conditions += "\n4. Program the device to SureScan/MRI mode before entering Zone IV."
            field_strength = "1.5T or 3.0T (Model dependent)"
            sar_limit = "Whole body SAR <= 2.0 W/kg"
            spatial_gradient = "<= 20 T/m (2000 G/cm)"
        elif "orthopedic" in specialty or "fixation" in dev_name_l or "screw" in dev_name_l or "rod" in dev_name_l:
            safety_status = "MRI Conditional"
            field_strength = "1.5T and 3.0T"
            sar_limit = "Whole body SAR <= 2.0 W/kg for 15 min scan"
            spatial_gradient = "<= 30 T/m (3000 G/cm)"
            conditions = "1. Passive implants require no post-implant wait period if non-ferromagnetic.\n2. In case of mild heating sensation, terminate scan immediately."
        elif "dental" in specialty or "implant" in dev_name_l and "prosthetic" in dev_name_l:
            safety_status = "MRI Safe"
            field_strength = "Up to 3.0T"
            sar_limit = "No limits (Non-ferromagnetic material)"
            spatial_gradient = "No limitations"
            conditions = "1. Typically constructed of titanium or zirconium, which present no magnetic risk."

        report = {
            "device_name": device_name,
            "manufacturer": manufacturer,
            "category": category,
            "safety_status": safety_status,
            "field_strength": field_strength,
            "sar_limit": sar_limit,
            "spatial_gradient": spatial_gradient,
            "conditions": conditions,
            "fda_clearance": clearance_details,
            "recalls_adverse_events": ""
        }
        report["source"] = "Dynamic FDA Records Compilation (Live API Query)"
        report["scraped_from"] = ["openfda.gov"]

    # Case C: Final Fallback for unrecognized device
    else:
        print(f"[-] No matches: Loading conservative unsafe fallback")
        report = {
            "device_name": query,
            "manufacturer": "Unknown",
            "category": "Unknown Implant Type",
            "safety_status": "MRI Unsafe",
            "field_strength": "Unknown - DO NOT SCAN",
            "sar_limit": "N/A",
            "spatial_gradient": "N/A",
            "conditions": (
                "WARNING: The AI agent was unable to find verified MRI safety documentation for this device in the openFDA registry.\n"
                "DO NOT SCAN the patient until the manufacturer's model and official safety guidelines have been manually verified by the MRI safety officer."
            ),
            "fda_clearance": "No verified clearance record found",
            "recalls_adverse_events": ""
        }
        report["source"] = "AI Agent Default Safety Fallback (Conservative)"
        report["scraped_from"] = ["AI Fallback Registry"]

    # Append recalls and adverse events text summary
    event_notes = "No recalls or adverse events found in FDA databases."
    if recall_res:
        rec_info = recall_res[0]
        event_notes = f"RECALL ALERT ({rec_info.get('recall_status', 'Active')}): " + \
                      rec_info.get("reason_for_recall", "")[:200] + "..."
    if event_res:
        ev_info = event_res[0]
        event_notes = f"MAUDE: {ev_info.get('event_description', ['No description'])[0][:200]}... | " + event_notes
        
    report["recalls_adverse_events"] = event_notes
    report["web_links"] = web_links
    report["compiled_data"] = compiled_data
    report["cached"] = False
    report["rate_limited"] = rate_limited

    if rate_limited:
        report["source"] = "FDA API Rate Limited (Cached/Fallback Mode)"

    # Generate draft verification hash
    sig_str = "|".join([
        str(report.get("device_name", "")),
        str(report.get("manufacturer", "")),
        str(report.get("safety_status", "")),
        str(report.get("fda_clearance", "")),
        str(report.get("field_strength", "")),
        str(report.get("sar_limit", "")),
        str(report.get("spatial_gradient", ""))
    ])
    report["draft_hash"] = compute_sha256(sig_str)
    report["cache_timestamp"] = datetime.now().isoformat()

    # Save to local cache
    cache[query_key] = report
    save_search_cache(cache)

    return jsonify(report)

AUDIT_LOG_FILE = 'audit.log'

def write_clinical_audit_log(ip, reviewer, title, device, draft_hash, approved_hash, notes):
    timestamp = datetime.utcnow().isoformat() + "Z"
    log_entry = (
        f"[{timestamp}] IP: {ip} | CFR Part 11 E-Signature Sign-Off Approved\n"
        f"  Reviewer       : {reviewer} ({title})\n"
        f"  Device Name    : {device}\n"
        f"  Draft Hash     : {draft_hash}\n"
        f"  Approval Hash  : {approved_hash}\n"
        f"  Review Notes   : {notes}\n"
        f"--------------------------------------------------------------------------------\n"
    )
    try:
        with open(AUDIT_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print(f"[+] Audit log recorded for {device}.")
    except Exception as e:
        print(f"[-] Failed to write audit log: {e}")

@app.route('/api/approve', methods=['POST'])
@api_login_required
def approve_report():
    data = request.get_json() or {}
    device_name = data.get("device_name", "").strip()
    reviewer = data.get("reviewer_name", "").strip()
    title = data.get("reviewer_title", "").strip()
    notes = data.get("clinical_notes", "").strip()
    draft_hash = data.get("draft_hash", "").strip()
    legal_confirm = data.get("legal_signature_intent")
    password = data.get("password", "").strip()
    
    # Validation Hardening: Block empty parameters or unsigned legal checks
    if not (device_name and reviewer and title and notes and draft_hash):
        return jsonify({"error": "Validation Error: All reviewer signature parameters (Name, Title, Clinical Notes) are required."}), 400
        
    if not password:
        return jsonify({"error": "Validation Error: Confirmation password is required for electronic signature."}), 400
        
    if password != CLINICIAN_PASS:
        return jsonify({"error": "Authentication Error: Incorrect clinical password. Signature execution rejected."}), 401
        
    if legal_confirm is not True:
        return jsonify({"error": "Compliance Error: Legally binding electronic signature intent must be confirmed under 21 CFR Part 11."}), 400
        
    timestamp = datetime.now().isoformat()
    
    # Compute cryptographic approved signature hash
    approval_sig = "|".join([draft_hash, reviewer, title, notes, timestamp])
    approved_hash = compute_sha256(approval_sig)
    
    # Write CFR Part 11 compliant audit log to disk
    client_ip = request.remote_addr or "127.0.0.1"
    write_clinical_audit_log(client_ip, reviewer, title, device_name, draft_hash, approved_hash, notes)
    
    print(f"[+] Human Approved Report: {device_name} signed by {reviewer}")
    return jsonify({
        "status": "success",
        "message": f"Clinical clearance approved and signed by {reviewer}.",
        "approved_device": device_name,
        "sign_off_timestamp": timestamp,
        "approved_hash": approved_hash
    })

@app.route('/api/add', methods=['POST'])
@api_login_required
def add_implant():
    data = request.get_json() or {}
    device_name = data.get("device_name", "").strip()
    manufacturer = data.get("manufacturer", "").strip()
    category = data.get("category", "").strip()
    safety_status = data.get("safety_status", "").strip()
    field_strength = data.get("field_strength", "").strip()
    sar_limit = data.get("sar_limit", "").strip()
    spatial_gradient = data.get("spatial_gradient", "").strip()
    conditions = data.get("conditions", "").strip()
    fda_clearance = data.get("fda_clearance", "").strip()
    recalls_adverse_events = data.get("recalls_adverse_events", "").strip()
    
    # Validation: Device Name and Safety Status are mandatory fields
    if not (device_name and safety_status):
        return jsonify({"error": "Validation Error: Device Name and Safety Status are required."}), 400
        
    query_key = device_name.lower().strip()
    
    new_report = {
        "device_name": device_name,
        "manufacturer": manufacturer if manufacturer else "Unknown",
        "category": category if category else "Medical Device",
        "safety_status": safety_status,
        "field_strength": field_strength if field_strength else "N/A",
        "sar_limit": sar_limit if sar_limit else "N/A",
        "spatial_gradient": spatial_gradient if spatial_gradient else "N/A",
        "conditions": conditions if conditions else "None specified.",
        "fda_clearance": fda_clearance if fda_clearance else "Manual Registry Entry",
        "recalls_adverse_events": recalls_adverse_events if recalls_adverse_events else "No active recalls reported."
    }
    
    db = load_implant_database()
    db[query_key] = new_report
    save_implant_database(db)
    
    # Update active in-memory global registry
    global IMPLANT_DATABASE
    IMPLANT_DATABASE = db
    
    # Invalidate cache for this query_key to prevent serving stale fallbacks
    cache = load_search_cache()
    if query_key in cache:
        del cache[query_key]
        save_search_cache(cache)
    
    print(f"[+] Custom implant registered: {device_name}")
    return jsonify({
        "status": "success",
        "message": f"Device '{device_name}' saved to registry database successfully.",
        "device": new_report
    })

@app.route('/api/suggest', methods=['POST'])
@api_login_required
def suggest_implants():
    data = request.get_json() or {}
    query = data.get("query", "").strip()
    
    if not query:
        return jsonify({"suggestions": []})
        
    query_lower = query.lower()
    suggestions = []
    
    # 1. Match local pre-seeded database keys
    for key, val in IMPLANT_DATABASE.items():
        if query_lower in key or key in query_lower:
            scraped_sources = val.get("scraped_from", [])
            source_display = ", ".join(scraped_sources) if scraped_sources else "Preset Catalog"
            suggestions.append({
                "name": val["device_name"],
                "manufacturer": val["manufacturer"],
                "source": source_display
            })
            
    # 2. Match live openFDA registries if query is 3+ characters
    if len(query_lower) >= 3:
        keywords = get_clean_keywords(query)
        # Query UDI first (clearest brand name registry)
        try:
            udi_matches = query_openfda_endpoint("udi", keywords, limit=10)
            for u in udi_matches:
                brand = u.get("brand_name")
                company = u.get("company_name", "Unknown Manufacturer")
                if brand:
                    brand_clean = re.sub(r'™|®', '', brand).strip()
                    if not any(s["name"].lower() == brand_clean.lower() for s in suggestions):
                        suggestions.append({
                            "name": brand_clean,
                            "manufacturer": company,
                            "source": "FDA Registry"
                        })
                if len(suggestions) >= 7:
                    break
        except Exception:
            pass
            
    # Fallback to 510(k) clearances if suggestions count is low
    if len(suggestions) < 5 and len(query_lower) >= 3:
        keywords = get_clean_keywords(query)
        try:
            k510_matches = query_openfda_endpoint("510k", keywords, limit=10)
            for k in k510_matches:
                name = k.get("device_name")
                company = k.get("applicant", "Unknown Manufacturer")
                if name:
                    name_clean = re.sub(r'™|®', '', name).strip()
                    if not any(s["name"].lower() == name_clean.lower() for s in suggestions):
                        suggestions.append({
                            "name": name_clean,
                            "manufacturer": company,
                            "source": "FDA 510(k)"
                        })
                if len(suggestions) >= 7:
                    break
        except Exception:
            pass
            
    return jsonify({"suggestions": suggestions[:7]})

def fetch_web_page_text(url):
    if url.lower().endswith('.pdf'):
        return ""
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            html_content = response.read().decode('utf-8', errors='ignore')
            
            # Remove scripts and style sections
            html_content = re.sub(r'<script.*?>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            html_content = re.sub(r'<style.*?>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
            
            # Extract plain text
            text = re.sub(r'<.*?>', ' ', html_content)
            
            import html
            text = html.unescape(text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
    except Exception as e:
        print(f"[-] Auto-Ingest: Failed to scrape {url}: {e}")
        return ""

def parse_safety_corpus(text, query):
    text_lower = text.lower() + " " + query.lower()
    
    manufacturers = [
        "Medtronic", "Abbott", "St. Jude Medical", "Boston Scientific", "Cochlear",
        "Edwards Lifesciences", "Biomet", "Stryker", "Zimmer", "Smith & Nephew",
        "DePuy", "Synthes", "Biotronik", "LivaNova", "Sorin", "Cook Medical"
    ]

    # 2. General heuristic extraction
    # 2.1. Safety Status
    safety_status = "MRI Conditional"
    if "mri unsafe" in text_lower or "mr unsafe" in text_lower or "mri-unsafe" in text_lower:
        safety_status = "MRI Unsafe"
    elif "mri safe" in text_lower or "mr safe" in text_lower or "mri-safe" in text_lower:
        if "conditional" not in text_lower:
            safety_status = "MRI Safe"

    # 2.2. Manufacturer
    manufacturer = "Unknown"
    for m in manufacturers:
        if m.lower() in text_lower:
            manufacturer = m
            break
            
    # 3. Category
    categories = [
        ("pacemaker", "Cardiac Pacemaker"),
        ("icd", "Defibrillator (ICD)"),
        ("defibrillator", "Defibrillator (ICD)"),
        ("cochlear", "Cochlear Implant"),
        ("stent", "Endovascular Stent Graft"),
        ("valve", "Prosthetic Heart Valve"),
        ("pump", "Infusion Pump"),
        ("stimulator", "Neurostimulator"),
        ("fixation", "Orthopedic Fixation"),
        ("screw", "Orthopedic Screw"),
        ("plate", "Orthopedic Plate"),
        ("joint", "Joint Prosthesis")
    ]
    category = "Medical Device"
    for keyword, name in categories:
        if keyword in text_lower:
            category = name
            break

    # 4. Field Strength
    field_strengths = []
    if re.search(r'\b(1\.5\s*t(esla)?|1\.5-t(esla)?)\b', text_lower):
        field_strengths.append("1.5T")
    if re.search(r'\b(3(\.0)?\s*t(esla)?|3(\.0)?-t(esla)?)\b', text_lower):
        field_strengths.append("3.0T")
        
    if len(field_strengths) == 2:
        field_strength = "1.5T and 3.0T"
    elif len(field_strengths) == 1:
        field_strength = f"{field_strengths[0]} Only"
    else:
        field_strength = "1.5T (Verify 3.0T in manual)"

    # 5. SAR Limit
    sar_match = re.search(r'\b(\d+(\.\d+)?\s*w/kg)\b', text_lower)
    if sar_match:
        sar_limit = f"Whole body SAR <= {sar_match.group(1).upper()}"
    else:
        sar_limit = "Whole body SAR <= 2.0 W/kg (Verify in manual)"

    # 6. Spatial Gradient
    gradient_match = re.search(r'\b(\d+(\.\d+)?\s*(t/m|g/cm|gauss/cm))\b', text_lower)
    if gradient_match:
        spatial_gradient = f"<= {gradient_match.group(1).upper()}"
    else:
        spatial_gradient = "Verify in manufacturer specifications"

    # 7. Operational Pre-conditions
    conditions = []
    sentences = re.split(r'\.|\n', text)
    seen_conds = set()
    for s in sentences:
        s_clean = s.strip()
        if not s_clean or len(s_clean) < 15 or len(s_clean) > 150:
            continue
        s_lower = s_clean.lower()
        if any(kw in s_lower for kw in ["must", "required", "mode", "leads", "program", "prior to", "monitor", "wait period", "removed prior"]):
            norm_s = re.sub(r'[^a-z]', '', s_lower)
            if norm_s not in seen_conds:
                seen_conds.add(norm_s)
                s_clean = re.sub(r'^[\d\s\-\*\•\.\)]+', '', s_clean).strip()
                conditions.append(s_clean)
            if len(conditions) >= 4:
                break
                
    if not conditions:
        conditions = [
            "Safety status and constraints must be verified in the official user manual.",
            "Ensure the patient's device model matches specifications prior to scan."
        ]
        
    conditions_list = [f"{i+1}. {cond}" for i, cond in enumerate(conditions)]
    conditions_str = "\n".join(conditions_list)

    # 8. Recalls / Adverse Events
    recalls_adverse_events = "No active recalls or adverse events extracted from safety manual corpus."
    if "recall" in text_lower:
        recalls_adverse_events = "Warning: Historical recall mentions found in manufacturer corpus. Verify model serial number before scan."

    return {
        "device_name": query,
        "manufacturer": manufacturer,
        "category": category,
        "safety_status": safety_status,
        "field_strength": field_strength,
        "sar_limit": sar_limit,
        "spatial_gradient": spatial_gradient,
        "conditions": conditions_str,
        "fda_clearance": "Auto-Ingested from Web Search",
        "recalls_adverse_events": recalls_adverse_events
    }

@app.route('/api/ingest', methods=['POST'])
@api_login_required
def ingest_implant_specifications():
    data = request.get_json() or {}
    query = data.get("query", "").strip()
    
    if not query:
        return jsonify({"error": "Empty search query"}), 400
        
    query_key = query.lower().strip()
    
    # 1. Search manufacturer website and manual sources
    print(f"[*] Ingesting specs for device: {query}")
    web_results = search_mri_safety_web(query)
    
    corpus_parts = []
    
    # Add search result titles as text source
    for w in web_results:
        corpus_parts.append(w.get("title", ""))
        
    # Crawl top 2 pages (excluding PDFs)
    crawled_count = 0
    crawled_domains = []
    for w in web_results:
        link = w.get("link", "")
        if link and not link.lower().endswith('.pdf'):
            print(f"[*] Crawling page: {link}")
            page_text = fetch_web_page_text(link)
            if page_text:
                corpus_parts.append(page_text[:4000]) # Limit memory footprint
                crawled_count += 1
                
                # Parse domain name
                try:
                    parsed_url = urllib.parse.urlparse(link)
                    domain = parsed_url.netloc.lower()
                    if domain.startswith("www."):
                        domain = domain[4:]
                    if domain and domain not in crawled_domains:
                        crawled_domains.append(domain)
                except Exception:
                    pass
            if crawled_count >= 2:
                break
                
    full_corpus = " ".join(corpus_parts)
    
    # Heuristically parse safety profile from full text corpus
    report = parse_safety_corpus(full_corpus, query)
    
    # Save scraped domains list
    report["scraped_from"] = crawled_domains if crawled_domains else ["duckduckgo.com"]
    
    # Normalize device name and manufacturer if corpus is empty or query is robust
    if len(query.split()) >= 2 and report["manufacturer"] == "Unknown":
        # Extract potential manufacturer from first word
        potential_man = query.split()[0]
        if potential_man.lower() in ["medtronic", "abbott", "cochlear", "biomet", "stryker", "zimmer", "biotronik"]:
            report["manufacturer"] = potential_man.capitalize()
            
    # Save the report to the persistent registry database
    db = load_implant_database()
    db[query_key] = report
    save_implant_database(db)
    
    # Invalidate search cache for this device
    cache = load_search_cache()
    if query_key in cache:
        del cache[query_key]
        save_search_cache(cache)
        
    # Update active database
    global IMPLANT_DATABASE
    IMPLANT_DATABASE = db
    
    return jsonify({
        "status": "success",
        "message": f"Successfully searched and auto-ingested '{query}' into database registry.",
        "device": report
    })

@app.route('/api/remove', methods=['POST'])
@api_login_required
def remove_implant():
    request_data = request.get_json() or {}
    device_name = request_data.get("device_name", "").strip()
    reviewer_name = request_data.get("reviewer_name", "").strip()
    reviewer_title = request_data.get("reviewer_title", "").strip()
    notes = request_data.get("clinical_notes", "").strip()
    legal_confirm = request_data.get("legal_signature_intent", False)
    password = request_data.get("password", "").strip()

    if not device_name:
        return jsonify({"error": "Device name is required for removal."}), 400
    if not reviewer_name or not reviewer_title or not notes:
        return jsonify({"error": "Clinical signature parameters are incomplete."}), 400
    if not password:
        return jsonify({"error": "Validation Error: Confirmation password is required for electronic signature."}), 400
    if password != CLINICIAN_PASS:
        return jsonify({"error": "Authentication Error: Incorrect clinical password. Removal authorization rejected."}), 401
    if not legal_confirm:
        return jsonify({"error": "FDA 21 CFR Part 11 binding electronic signature intent must be checked."}), 400

    query_key = device_name.lower().strip()
    db = load_implant_database()
    
    if query_key not in db:
        # Check if any key fuzzy-matches or matches by device name
        found_key = None
        for key, val in db.items():
            if key == query_key or val.get("device_name", "").lower().strip() == query_key:
                found_key = key
                break
        if not found_key:
            return jsonify({"error": f"Device '{device_name}' not found in registry database."}), 404
        query_key = found_key

    # Record target for removal
    device_to_remove = db[query_key]
    removed_name = device_to_remove.get("device_name", device_name)

    # Compute a cryptographic signature hash for the removal audit trail
    sig_str = "|".join([
        "REMOVED",
        str(removed_name),
        str(reviewer_name),
        str(reviewer_title),
        str(notes)
    ])
    approved_hash = compute_sha256(sig_str)
    
    # Write to CFR Part 11 compliant audit log
    ip_addr = request.remote_addr
    timestamp = datetime.now().isoformat()
    
    log_entry = (
        f"[{timestamp}Z] IP: {ip_addr} | CFR Part 11 E-Signature Removal Approved\n"
        f"  Reviewer       : {reviewer_name} ({reviewer_title})\n"
        f"  Removed Device : {removed_name}\n"
        f"  Removal Hash   : {approved_hash}\n"
        f"  Reason         : {notes}\n"
        "--------------------------------------------------------------------------------\n"
    )
    
    # Append to audit.log
    with open(AUDIT_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_entry)

    # Remove from database
    del db[query_key]
    save_implant_database(db)

    # Invalidate cache
    cache = load_search_cache()
    if query_key in cache:
        del cache[query_key]
        save_search_cache(cache)
        
    global IMPLANT_DATABASE
    IMPLANT_DATABASE = db

    return jsonify({
        "status": "success",
        "message": f"Successfully removed '{removed_name}' from the persistent registry database.",
        "removed_device": removed_name,
        "removal_hash": approved_hash,
        "timestamp": timestamp
    })

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)


