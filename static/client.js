// Implant Safety Agent - Client Application Logic

document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    initRecentSearches();
});

// Recent Searches configuration
const DEFAULT_PRESETS = [
    { query: "Medtronic Advisa", label: "Medtronic Pacemaker", icon: "fa-heart-pulse" },
    { query: "Starr Edwards Valve", label: "Starr-Edwards Heart Valve", icon: "fa-circle-dot" },
    { query: "Cochlear Nucleus 7", label: "Cochlear Implant", icon: "fa-ear-deaf" },
    { query: "AneuRx Stent Graft", label: "AneuRx Stent Graft", icon: "fa-dna" }
];

function initRecentSearches() {
    let recent = localStorage.getItem("recent_mri_searches");
    if (!recent) {
        // Initialize with default seeds
        const initial = DEFAULT_PRESETS.map(p => ({
            query: p.query,
            label: p.label,
            icon: p.icon
        }));
        localStorage.setItem("recent_mri_searches", JSON.stringify(initial));
    }
    renderRecentSearches();
}

function saveRecentSearch(query, deviceName = null) {
    let recent = [];
    try {
        recent = JSON.parse(localStorage.getItem("recent_mri_searches")) || [];
    } catch(e) {
        recent = [];
    }

    // Determine icon based on query or deviceName
    let icon = "fa-clock-rotate-left";
    let label = deviceName || query;
    const qLower = label.toLowerCase();
    
    if (qLower.includes("pacemaker") || qLower.includes("advisa")) {
        icon = "fa-heart-pulse";
    } else if (qLower.includes("valve") || qLower.includes("starr")) {
        icon = "fa-circle-dot";
    } else if (qLower.includes("cochlear") || qLower.includes("nucleus")) {
        icon = "fa-ear-deaf";
    } else if (qLower.includes("stent") || qLower.includes("aneurx")) {
        icon = "fa-dna";
    }

    // Remove existing query to bring it to the top
    recent = recent.filter(item => item.query.toLowerCase() !== query.toLowerCase());

    // Insert at front
    recent.unshift({ query: query, label: label, icon: icon });

    // Limit to 4
    recent = recent.slice(0, 4);

    localStorage.setItem("recent_mri_searches", JSON.stringify(recent));
    renderRecentSearches();
}

function renderRecentSearches() {
    const container = document.getElementById("recent-searches-list");
    if (!container) return;

    container.innerHTML = "";
    let recent = [];
    try {
        recent = JSON.parse(localStorage.getItem("recent_mri_searches")) || [];
    } catch(e) {
        recent = [];
    }

    recent.forEach(item => {
        const btn = document.createElement("button");
        btn.className = "preset-btn";
        btn.dataset.query = item.query;
        btn.innerHTML = `<i class="fa-solid ${item.icon}"></i> ${escapeHtml(item.label)}`;
        
        btn.addEventListener("click", () => {
            const searchInput = document.getElementById("search-input");
            if (searchInput) searchInput.value = item.query;
            const suggestionsDropdown = document.getElementById("search-suggestions");
            if (suggestionsDropdown) suggestionsDropdown.style.display = "none";
            runSafetyAgent(item.query);
        });

        container.appendChild(btn);
    });
}

let currentDeviceData = null;
let suggestTimeout = null;

// Escape HTML utility for XSS prevention
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function setupEventListeners() {
    const searchForm = document.getElementById("search-form");
    const searchInput = document.getElementById("search-input");
    const approvalForm = document.getElementById("approval-form");
    const printBtn = document.getElementById("print-btn");
    const suggestionsDropdown = document.getElementById("search-suggestions");
    const toggleAddDeviceBtn = document.getElementById("toggle-add-device-btn");
    const cancelAddDeviceBtn = document.getElementById("cancel-add-device-btn");
    const addImplantForm = document.getElementById("add-implant-form");

    // Search Form Submit (User manually presses Enter or clicks button)
    searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const query = searchInput.value.trim();
        if (query) {
            suggestionsDropdown.style.display = "none";
            runSafetyAgent(query);
        }
    });

    // Input listening with 300ms debounce for Autocomplete Suggestions
    searchInput.addEventListener("input", () => {
        clearTimeout(suggestTimeout);
        const query = searchInput.value.trim();
        if (query.length < 3) {
            suggestionsDropdown.style.display = "none";
            return;
        }
        suggestTimeout = setTimeout(() => {
            fetchSuggestions(query);
        }, 300);
    });

    // Approval Form Submit
    approvalForm.addEventListener("submit", (e) => {
        e.preventDefault();
        handleHumanApproval();
    });

    // Print Button Click
    printBtn.addEventListener("click", () => {
        window.print();
    });

    // Click outside search container closes suggestions
    document.addEventListener("click", (e) => {
        const searchBoxContainer = document.querySelector(".search-box-container");
        if (searchBoxContainer && !searchBoxContainer.contains(e.target)) {
            suggestionsDropdown.style.display = "none";
        }
    });

    // Pressing Escape closes suggestions
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            suggestionsDropdown.style.display = "none";
        }
    });

    // Setup Dossier Tab Switching
    const tabBtns = document.querySelectorAll(".tab-btn");
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            // Remove active class from all buttons
            tabBtns.forEach(b => b.classList.remove("active"));
            // Add active to clicked button
            btn.classList.add("active");
            
            // Hide all tab contents
            const tabContents = document.querySelectorAll(".tab-content");
            tabContents.forEach(tc => tc.classList.remove("active"));
            
            // Show target tab content
            const targetId = btn.dataset.tab;
            const targetContent = document.getElementById(targetId);
            if (targetContent) {
                targetContent.classList.add("active");
            }
        });
    });

    // Custom Implant Registration View Toggle
    if (toggleAddDeviceBtn) {
        toggleAddDeviceBtn.addEventListener("click", () => {
            document.getElementById("report-view-default").style.display = "none";
            document.getElementById("report-view-active").style.display = "none";
            document.getElementById("report-view-add-implant").style.display = "flex";
        });
    }

    // Cancel Registration and Restore View
    if (cancelAddDeviceBtn) {
        cancelAddDeviceBtn.addEventListener("click", () => {
            document.getElementById("report-view-add-implant").style.display = "none";
            if (currentDeviceData) {
                document.getElementById("report-view-active").style.display = "flex";
            } else {
                document.getElementById("report-view-default").style.display = "flex";
            }
            if (addImplantForm) {
                addImplantForm.reset();
            }
        });
    }

    // Submit Custom Implant to Database Registry
    if (addImplantForm) {
        addImplantForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            
            const deviceName = document.getElementById("add-dev-name").value.trim();
            const manufacturer = document.getElementById("add-dev-manufacturer").value.trim();
            const category = document.getElementById("add-dev-category").value.trim();
            const fdaClearance = document.getElementById("add-dev-fda").value.trim();
            const safetyStatus = document.getElementById("add-dev-safety").value;
            const fieldStrength = document.getElementById("add-const-field").value.trim();
            const sarLimit = document.getElementById("add-const-sar").value.trim();
            const spatialGradient = document.getElementById("add-const-gradient").value.trim();
            const conditions = document.getElementById("add-conditions").value.trim();
            const recalls = document.getElementById("add-alerts").value.trim();

            if (!deviceName || !safetyStatus) {
                alert("Validation Error: Device Name and Safety Status are required.");
                return;
            }

            try {
                const response = await fetch("/api/add", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        device_name: deviceName,
                        manufacturer: manufacturer,
                        category: category,
                        fda_clearance: fdaClearance,
                        safety_status: safetyStatus,
                        field_strength: fieldStrength,
                        sar_limit: sarLimit,
                        spatial_gradient: spatialGradient,
                        conditions: conditions,
                        recalls_adverse_events: recalls
                    })
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.error || "Registry error");
                }

                const data = await response.json();
                alert(`Clinical Registry: Implant '${deviceName}' successfully registered.`);
                
                // Reset form and swap views
                addImplantForm.reset();
                document.getElementById("report-view-add-implant").style.display = "none";
                
                // Update search field and execute safety agent verification immediately
                searchInput.value = deviceName;
                runSafetyAgent(deviceName);

            } catch (error) {
                console.error("[-] Custom implant registration failed:", error);
                alert(`Error: ${error.message}`);
            }
        });
    }

    // Auto-Ingest from Left Sidebar Controls
    const ingestInput = document.getElementById("ingest-input");
    const ingestBtn = document.getElementById("ingest-btn");
    if (ingestBtn && ingestInput) {
        const triggerIngest = () => {
            const query = ingestInput.value.trim();
            if (query) {
                ingestInput.value = "";
                runAutoIngestion(query);
            }
        };
        ingestBtn.addEventListener("click", triggerIngest);
        ingestInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                triggerIngest();
            }
        });
    }

    // Trigger Ingest from Fallback Action Prompt Card
    const triggerFallbackIngestBtn = document.getElementById("trigger-fallback-ingest-btn");
    if (triggerFallbackIngestBtn) {
        triggerFallbackIngestBtn.addEventListener("click", () => {
            if (currentDeviceData && currentDeviceData.device_name) {
                runAutoIngestion(currentDeviceData.device_name);
            }
        });
    }
}

// Fetch Autocomplete Suggestions from Backend API
async function fetchSuggestions(query) {
    try {
        const response = await fetch("/api/suggest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: query })
        });
        if (!response.ok) throw new Error("Suggestions fetch failed");
        
        const data = await response.json();
        renderSuggestions(data.suggestions);
    } catch (error) {
        console.error("[-] Suggestions API error:", error);
    }
}

// Render Suggestions Dropdown list
function renderSuggestions(suggestions) {
    const dropdown = document.getElementById("search-suggestions");
    dropdown.innerHTML = "";
    
    if (!suggestions || suggestions.length === 0) {
        dropdown.style.display = "none";
        return;
    }
    
    suggestions.forEach(s => {
        const item = document.createElement("div");
        item.className = "suggestion-item";
        
        const title = document.createElement("span");
        title.className = "suggestion-title";
        title.textContent = s.name;
        
        const meta = document.createElement("div");
        meta.className = "suggestion-meta";
        
        const manSpan = document.createElement("span");
        manSpan.textContent = s.manufacturer;
        
        const badge = document.createElement("span");
        badge.className = "suggestion-badge";
        if (s.source.toLowerCase().includes("mrisafety.com")) {
            badge.style.background = "rgba(59, 130, 246, 0.15)";
            badge.style.color = "var(--accent-blue)";
        } else {
            badge.classList.add("preset");
        }
        badge.textContent = s.source;
        
        meta.appendChild(manSpan);
        meta.appendChild(badge);
        item.appendChild(title);
        item.appendChild(meta);
        
        // Suggestion selected trigger
        item.addEventListener("click", () => {
            const searchInput = document.getElementById("search-input");
            searchInput.value = s.name;
            dropdown.style.display = "none";
            runSafetyAgent(s.name);
        });
        
        dropdown.appendChild(item);
    });
    
    dropdown.style.display = "block";
}

// Run Step-by-Step AI Verification Agent (with simulated logging delays)
function runSafetyAgent(query) {
    const agentLog = document.getElementById("agent-log");
    const defaultView = document.getElementById("report-view-default");
    const activeView = document.getElementById("report-view-active");
    const statusBadge = document.getElementById("status-badge");
    const approvalForm = document.getElementById("approval-form");
    const signatureStamp = document.getElementById("signature-stamp");
    const apiStatus = document.getElementById("api-status-badge");

    // Reset UI state
    defaultView.style.display = "flex";
    activeView.style.display = "none";
    const disambigView = document.getElementById("report-view-disambiguation");
    if (disambigView) disambigView.style.display = "none";
    const addImplantView = document.getElementById("report-view-add-implant");
    if (addImplantView) addImplantView.style.display = "none";
    statusBadge.className = "report-status-badge pending";
    statusBadge.innerHTML = `<i class="fa-solid fa-clock"></i> PENDING CLINICAL REVIEW`;
    approvalForm.style.display = "block";
    signatureStamp.style.display = "none";
    approvalForm.reset();

    // Reset connection status badge
    apiStatus.className = "api-status-badge live";
    apiStatus.innerHTML = `<i class="fa-solid fa-circle-check"></i> FDA Connection: Live`;

    // Clear and start log
    agentLog.innerHTML = "";
    
    const logs = [
        { text: "⚙️ Initializing Implant Safety Agent...", delay: 0, type: "info" },
        { text: `🔍 Target Device Query: "${query}"`, delay: 400, type: "info" },
        { text: "📂 Querying FDA UDI, PMA, 510(k), and De Novo registries...", delay: 1000, type: "info" },
        { text: "🚨 Scanning MAUDE database for adverse event reports...", delay: 1800, type: "info" },
        { text: "🌐 Scraping manufacturer safety specifications & MR conditional sheets...", delay: 2500, type: "info" },
        { text: "🧠 Analyzing magnetic field limits (1.5T/3T) and SAR boundaries...", delay: 3200, type: "warning" },
        { text: "📝 Compiling clinical safety clearance draft...", delay: 3800, type: "success" }
    ];

    logs.forEach(log => {
        setTimeout(() => {
            appendLog(log.text, log.type);
        }, log.delay);
    });

    // Send backend request after logging completes
    setTimeout(async () => {
        try {
            const response = await fetch("/api/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: query })
            });

            if (!response.ok) throw new Error("API request failed");
            
            const data = await response.json();
            currentDeviceData = data;
            
            // Check if response is a disambiguation payload
            if (data.disambiguation) {
                renderDisambiguation(data);
                appendLog(`[+] Agent Complete. Multiple matches found. Please select correct model.`, "warning");
                return;
            }
            
            // Save search to local storage and update recent UI
            saveRecentSearch(query, data.device_name);

            // Populate and show report
            renderReport(data);

            // Handle API status warning
            if (data.rate_limited) {
                apiStatus.className = "api-status-badge limited";
                apiStatus.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> FDA: Rate Limited`;
                appendLog(`[!] WARNING: FDA API rate limit reached. Operating in Fallback Cache Mode.`, "warning");
            }

            appendLog(`[+] Agent Complete. Report generated from source: ${data.source}`, "success");
            
        } catch (error) {
            apiStatus.className = "api-status-badge offline";
            apiStatus.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> FDA: Connection Failed`;
            appendLog(`[-] Error during agent verification: ${error.message}`, "error");
            alert("Verification agent encountered an error querying the backend database.");
        }
    }, 4200);
}

function appendLog(text, type = "info") {
    const agentLog = document.getElementById("agent-log");
    const logDiv = document.createElement("div");
    logDiv.className = `log-entry ${type}`;
    logDiv.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    agentLog.appendChild(logDiv);
    agentLog.scrollTop = agentLog.scrollHeight;
}

// Populate and render the compiled report
function renderReport(data) {
    const defaultView = document.getElementById("report-view-default");
    const activeView = document.getElementById("report-view-active");
    const reportIdText = document.getElementById("report-id");
    const safetyCard = document.getElementById("safety-card");
    const safetyIconDiv = document.getElementById("safety-icon-div");
    const safetyTitle = document.getElementById("safety-title");
    const safetyDesc = document.getElementById("safety-desc");

    // Generate custom report ID
    const randomHex = Math.floor(Math.random()*16777215).toString(16).toUpperCase();
    const dateStr = new Date().toISOString().slice(0,10).replace(/-/g,"");
    reportIdText.textContent = `REPORT-ID: IS-CLEAR-${dateStr}-${randomHex}`;

    // Display Cache Badge if serving from cache
    const cacheBadge = document.getElementById("cache-badge");
    if (data.cached) {
        cacheBadge.style.display = "inline-flex";
        cacheBadge.title = `Cached on: ${data.cache_timestamp}`;
    } else {
        cacheBadge.style.display = "none";
    }

    // Populate metadata
    document.getElementById("dev-name").textContent = data.device_name;
    document.getElementById("dev-manufacturer").textContent = data.manufacturer;
    document.getElementById("dev-category").textContent = data.category;
    document.getElementById("dev-fda").textContent = data.fda_clearance;

    // Populate manual verification link
    const manualAnchor = document.getElementById("manual-verification-anchor");
    if (manualAnchor) {
        if (data.manual_link) {
            manualAnchor.href = data.manual_link;
            manualAnchor.innerHTML = `<i class="fa-solid fa-arrow-up-right-from-square"></i> Open Manufacturer Verification Manual`;
        } else if (data.web_links && data.web_links.length > 0) {
            manualAnchor.href = data.web_links[0].link;
            manualAnchor.innerHTML = `<i class="fa-solid fa-arrow-up-right-from-square"></i> Verify on ${escapeHtml(data.web_links[0].title.slice(0, 30))}...`;
        } else {
            const qEscaped = encodeURIComponent(`${data.device_name} ${data.manufacturer} MRI safety manual`);
            manualAnchor.href = `https://duckduckgo.com/?q=${qEscaped}`;
            manualAnchor.innerHTML = `<i class="fa-solid fa-magnifying-glass"></i> Search Manufacturer Manuals`;
        }
    }

    // Populate ingestion sources
    const sourceBadgeRow = document.getElementById("source-badge-row");
    if (sourceBadgeRow) {
        sourceBadgeRow.innerHTML = "";
        const sources = data.scraped_from || ["Preset Catalog"];
        sources.forEach(src => {
            const badge = document.createElement("span");
            badge.className = "suggestion-badge preset";
            if (src.toLowerCase() === "mrisafety.com") {
                badge.style.background = "rgba(59, 130, 246, 0.15)";
                badge.style.color = "var(--accent-blue)";
            }
            badge.textContent = src;
            sourceBadgeRow.appendChild(badge);
        });
    }

    // Populate constraints
    document.getElementById("const-field").textContent = data.field_strength;
    document.getElementById("const-sar").textContent = data.sar_limit;
    document.getElementById("const-gradient").textContent = data.spatial_gradient;

    // Populate conditions list
    const condList = document.getElementById("conditions-list");
    condList.innerHTML = "";
    const conditions = data.conditions.split("\n");
    conditions.forEach(c => {
        if (c.trim()) {
            const li = document.createElement("li");
            li.textContent = c.replace(/^\d+\.\s*/, "");
            condList.appendChild(li);
        }
    });

    // Populate alerts
    document.getElementById("recalls-text").textContent = data.recalls_adverse_events;

    // Populate Dynamic safety checklist
    setupInteractiveChecklist(data.conditions);

    // Render Compiled FDA Dossier Tables & Lists
    renderCompiledDossier(data.compiled_data);

    // Populate verified web reference links
    const refLinksSection = document.getElementById("ref-links-section");
    const refLinksBox = document.getElementById("reference-links");
    refLinksBox.innerHTML = "";
    
    if (data.web_links && data.web_links.length > 0) {
        refLinksSection.style.display = "block";
        data.web_links.forEach(w => {
            const card = document.createElement("a");
            card.className = "ref-link-card";
            card.href = w.link;
            card.target = "_blank";
            
            const icon = document.createElement("i");
            icon.className = "fa-solid fa-arrow-up-right-from-square";
            
            const details = document.createElement("div");
            details.className = "ref-link-details";
            
            const titleSpan = document.createElement("span");
            titleSpan.className = "ref-link-title";
            titleSpan.textContent = w.title;
            
            const urlSpan = document.createElement("span");
            urlSpan.className = "ref-link-url";
            urlSpan.textContent = w.link;
            
            // Extract domain for source tagging
            let domain = "unknown";
            try {
                const url = new URL(w.link);
                domain = url.hostname.toLowerCase();
                if (domain.startsWith("www.")) {
                    domain = domain.substring(4);
                }
            } catch (e) {}
            
            const domainBadge = document.createElement("span");
            domainBadge.className = "suggestion-badge";
            domainBadge.style.marginLeft = "auto";
            domainBadge.style.fontSize = "10px";
            if (domain === "mrisafety.com") {
                domainBadge.style.background = "rgba(59, 130, 246, 0.15)";
                domainBadge.style.color = "var(--accent-blue)";
            } else {
                domainBadge.style.background = "rgba(16, 185, 129, 0.15)";
                domainBadge.style.color = "var(--status-safe)";
            }
            domainBadge.textContent = domain;
            
            details.appendChild(titleSpan);
            details.appendChild(urlSpan);
            card.appendChild(icon);
            card.appendChild(details);
            card.appendChild(domainBadge);
            refLinksBox.appendChild(card);
        });
    } else {
        refLinksSection.style.display = "none";
    }

    // Adjust Safety Card Theme depending on status
    const status = data.safety_status.toLowerCase();
    safetyCard.className = "safety-class-card"; // Reset classes
    
    if (status === "mri safe") {
        safetyCard.classList.add("safe");
        safetyIconDiv.innerHTML = `<i class="fa-solid fa-circle-check"></i>`;
        safetyTitle.textContent = "MRI Safe";
        safetyDesc.textContent = "The implant presents no additional risk under any MRI environment.";
    } else if (status === "mri conditional") {
        safetyCard.classList.add("conditional");
        safetyIconDiv.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i>`;
        safetyTitle.textContent = "MRI Conditional";
        safetyDesc.textContent = "The implant can be scanned safely ONLY under specific constraints detailed below.";
    } else {
        safetyCard.classList.add("unsafe");
        safetyIconDiv.innerHTML = `<i class="fa-solid fa-circle-xmark"></i>`;
        safetyTitle.textContent = "MRI Unsafe";
        safetyDesc.textContent = "DO NOT SCAN the patient. The implant presents severe risk in an MRI environment.";
    }

    // Show fallback auto-ingest prompt if the report is a fallback report
    const isFallback = data.source && data.source.includes("Default Safety Fallback");
    const fallbackPrompt = document.getElementById("fallback-ingest-prompt");
    if (fallbackPrompt) {
        fallbackPrompt.style.display = isFallback ? "flex" : "none";
    }

    // Toggle views
    defaultView.style.display = "none";
    activeView.style.display = "flex";
}

// Generate the checklist checkboxes based on pre-conditions
function setupInteractiveChecklist(conditionsStr) {
    const checklistBox = document.getElementById("clinical-checklist");
    const approveBtn = document.getElementById("approve-btn");
    checklistBox.innerHTML = "";
    approveBtn.disabled = true; // Disable initially

    const conditions = conditionsStr.split("\n");
    
    conditions.forEach((c, idx) => {
        const cleaned = c.trim().replace(/^\d+\.\s*/, "");
        if (cleaned) {
            const label = document.createElement("label");
            label.className = "checklist-item";
            
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.className = "checklist-cb";
            checkbox.id = `cb-cond-${idx}`;
            
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(cleaned));
            checklistBox.appendChild(label);
        }
    });

    // Add final clinician model-matching verification checkbox
    const finalLabel = document.createElement("label");
    finalLabel.className = "checklist-item";
    const finalCb = document.createElement("input");
    finalCb.type = "checkbox";
    finalCb.className = "checklist-cb";
    finalCb.id = "cb-final-match";
    finalLabel.appendChild(finalCb);
    finalLabel.appendChild(document.createTextNode("I verify that the patient's implant model matches the records compiled below."));
    checklistBox.appendChild(finalLabel);

    // Event listener to unlock approval button only when all checkboxes are checked
    const checkboxes = document.querySelectorAll(".checklist-cb");
    checkboxes.forEach(cb => {
        cb.addEventListener("change", () => {
            const allChecked = Array.from(checkboxes).every(c => c.checked);
            approveBtn.disabled = !allChecked;
        });
    });
}

// Map MRI status to Badge HMTL (escaped)
function getMriBadgeHtml(statusStr) {
    if (!statusStr) return `<span class="dossier-badge unknown">Unknown</span>`;
    const s = statusStr.toLowerCase();
    const cleanStatus = escapeHtml(statusStr);
    if (s.includes("conditional")) {
        return `<span class="dossier-badge conditional">MR Conditional</span>`;
    } else if (s.includes("safe") && !s.includes("unsafe")) {
        return `<span class="dossier-badge safe">MR Safe</span>`;
    } else if (s.includes("unsafe")) {
        return `<span class="dossier-badge unsafe">MR Unsafe</span>`;
    } else {
        return `<span class="dossier-badge unknown">${cleanStatus}</span>`;
    }
}

// Populate the Tabbed FDA Registry Dossier (Hardened with XSS escaping)
function renderCompiledDossier(compiledData) {
    const section = document.getElementById("dossier-section");
    if (!compiledData) {
        section.style.display = "none";
        return;
    }
    section.style.display = "block";

    // 1. UDI Registry
    const udiCount = compiledData.udi ? compiledData.udi.length : 0;
    document.getElementById("count-udi").textContent = udiCount;
    const udiTbody = document.getElementById("udi-table-body");
    udiTbody.innerHTML = "";
    if (udiCount > 0) {
        compiledData.udi.forEach(u => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>
                    <strong>${escapeHtml(u.brand_name || 'N/A')}</strong>
                    <span class="dossier-badge unknown" style="margin-left: 6px; font-size: 9px; padding: 1px 4px; vertical-align: middle;">FDA GUDID</span>
                </td>
                <td>${escapeHtml(u.company_name || 'N/A')}</td>
                <td>${getMriBadgeHtml(u.mri_safety)}</td>
                <td><small>${escapeHtml(u.catalog_number || 'No Catalog #')}<br>${escapeHtml(u.device_description ? u.device_description.slice(0,60) + '...' : '')}</small></td>
            `;
            udiTbody.appendChild(tr);
        });
    } else {
        udiTbody.innerHTML = `<tr><td colspan="4" class="empty-tab-state"><i class="fa-solid fa-folder-open"></i> No matching UDI records found.</td></tr>`;
    }

    // 2. PMA Approvals
    const pmaCount = compiledData.pma ? compiledData.pma.length : 0;
    document.getElementById("count-pma").textContent = pmaCount;
    const pmaList = document.getElementById("pma-list");
    pmaList.innerHTML = "";
    if (pmaCount > 0) {
        compiledData.pma.forEach(p => {
            const li = document.createElement("li");
            li.className = "dossier-item";
            li.innerHTML = `
                <div class="dossier-item-header">
                    <span class="dossier-item-title">
                        ${escapeHtml(p.trade_name || 'N/A')}
                        <span class="dossier-badge unknown" style="margin-left: 6px; font-size: 9px; padding: 1px 4px; vertical-align: middle;">FDA PMA</span>
                    </span>
                    <span class="dossier-badge safe">${escapeHtml(p.pma_number)}</span>
                </div>
                <div class="dossier-item-meta">Applicant: ${escapeHtml(p.applicant || 'Unknown')} | Generic: ${escapeHtml(p.generic_name || 'N/A')}</div>
                <div class="dossier-item-desc"><small>Specialty: ${escapeHtml(p.openfda?.medical_specialty_description || 'N/A')}</small></div>
            `;
            pmaList.appendChild(li);
        });
    } else {
        pmaList.innerHTML = `<div class="empty-tab-state"><i class="fa-solid fa-folder-open"></i> No matching PMA records found.</div>`;
    }

    // 3. 510(k) Clearances
    const k510Count = compiledData.k510 ? compiledData.k510.length : 0;
    document.getElementById("count-510k").textContent = k510Count;
    const k510List = document.getElementById("510k-list");
    k510List.innerHTML = "";
    if (k510Count > 0) {
        compiledData.k510.forEach(k => {
            const li = document.createElement("li");
            li.className = "dossier-item";
            li.innerHTML = `
                <div class="dossier-item-header">
                    <span class="dossier-item-title">
                        ${escapeHtml(k.device_name || 'N/A')}
                        <span class="dossier-badge unknown" style="margin-left: 6px; font-size: 9px; padding: 1px 4px; vertical-align: middle;">FDA 510(k)</span>
                    </span>
                    <span class="dossier-badge conditional">${escapeHtml(k.k_number)}</span>
                </div>
                <div class="dossier-item-meta">Applicant: ${escapeHtml(k.applicant || 'Unknown')}</div>
                <div class="dossier-item-desc"><small>Specialty: ${escapeHtml(k.openfda?.medical_specialty_description || 'N/A')}</small></div>
            `;
            k510List.appendChild(li);
        });
    } else {
        k510List.innerHTML = `<div class="empty-tab-state"><i class="fa-solid fa-folder-open"></i> No matching 510(k) records found.</div>`;
    }

    // 4. De Novo
    const denovoCount = compiledData.denovo ? compiledData.denovo.length : 0;
    document.getElementById("count-denovo").textContent = denovoCount;
    const dnList = document.getElementById("denovo-list");
    dnList.innerHTML = "";
    if (denovoCount > 0) {
        compiledData.denovo.forEach(d => {
            const li = document.createElement("li");
            li.className = "dossier-item";
            li.innerHTML = `
                <div class="dossier-item-header">
                    <span class="dossier-item-title">
                        ${escapeHtml(d.device_name || 'N/A')}
                        <span class="dossier-badge unknown" style="margin-left: 6px; font-size: 9px; padding: 1px 4px; vertical-align: middle;">FDA De Novo</span>
                    </span>
                    <span class="dossier-badge safe">${escapeHtml(d.denovo_number)}</span>
                </div>
                <div class="dossier-item-meta">Applicant: ${escapeHtml(d.applicant || 'Unknown')}</div>
            `;
            dnList.appendChild(li);
        });
    } else {
        dnList.innerHTML = `<div class="empty-tab-state"><i class="fa-solid fa-folder-open"></i> No matching De Novo records found.</div>`;
    }

    // 5. Recalls
    const recallsCount = compiledData.recalls ? compiledData.recalls.length : 0;
    document.getElementById("count-recalls").textContent = recallsCount;
    const recList = document.getElementById("recalls-list");
    recList.innerHTML = "";
    if (recallsCount > 0) {
        compiledData.recalls.forEach(r => {
            const li = document.createElement("li");
            li.className = "dossier-item";
            const isCompleted = (r.recall_status || "").toLowerCase() === "completed";
            const badgeClass = isCompleted ? "safe" : "unsafe";
            li.innerHTML = `
                <div class="dossier-item-header">
                    <span class="dossier-item-title">
                        Firm: ${escapeHtml(r.recalling_firm || 'N/A')}
                        <span class="dossier-badge unknown" style="margin-left: 6px; font-size: 9px; padding: 1px 4px; vertical-align: middle;">FDA Recalls</span>
                    </span>
                    <span class="dossier-badge ${badgeClass}">${escapeHtml(r.recall_status || 'Active')}</span>
                </div>
                <div class="dossier-item-meta">Reason: ${escapeHtml(r.reason_for_recall || 'N/A')}</div>
                <div class="dossier-item-desc"><small>Product: ${escapeHtml(r.product_description || 'N/A')}</small></div>
            `;
            recList.appendChild(li);
        });
    } else {
        recList.innerHTML = `<div class="empty-tab-state"><i class="fa-solid fa-folder-open"></i> No recalls found for this device.</div>`;
    }

    // 6. Adverse Events
    const eventsCount = compiledData.events ? compiledData.events.length : 0;
    document.getElementById("count-events").textContent = eventsCount;
    const evList = document.getElementById("events-list");
    evList.innerHTML = "";
    if (eventsCount > 0) {
        compiledData.events.forEach(e => {
            const li = document.createElement("li");
            li.className = "dossier-item";
            const desc = e.event_description && e.event_description[0] ? e.event_description[0] : 'No description available';
            li.innerHTML = `
                <div class="dossier-item-header">
                    <span class="dossier-item-title">
                        Event Source: ${escapeHtml(e.source_type || 'Unknown')}
                        <span class="dossier-badge unknown" style="margin-left: 6px; font-size: 9px; padding: 1px 4px; vertical-align: middle;">FDA MAUDE</span>
                    </span>
                    <span class="dossier-item-meta">Date: ${escapeHtml(e.date_of_event || 'N/A')}</span>
                </div>
                <div class="dossier-item-desc"><small>${escapeHtml(desc.slice(0, 300))}...</small></div>
            `;
            evList.appendChild(li);
        });
    } else {
        evList.innerHTML = `<div class="empty-tab-state"><i class="fa-solid fa-folder-open"></i> No adverse event reports found in MAUDE.</div>`;
    }
}

// Handle Human Review approval sign-off with 21 CFR Part 11 validation
async function handleHumanApproval() {
    const reviewerName = document.getElementById("reviewer-name").value.trim();
    const reviewerTitle = document.getElementById("reviewer-title").value.trim();
    const clinicalNotes = document.getElementById("clinical-notes").value.trim();
    const legalConfirm = document.getElementById("legal-signature-intent").checked;
    const password = document.getElementById("reviewer-password").value.trim();
    const statusBadge = document.getElementById("status-badge");
    const approvalForm = document.getElementById("approval-form");
    const signatureStamp = document.getElementById("signature-stamp");

    if (!reviewerName || !reviewerTitle || !clinicalNotes) {
        alert("Clinical signature parameters are incomplete.");
        return;
    }

    if (!password) {
        alert("Clinical confirmation password is required to execute signature.");
        return;
    }

    if (!legalConfirm) {
        alert("FDA 21 CFR Part 11 binding electronic signature intent must be checked.");
        return;
    }

    appendLog("[*] Submitting human clearance approval...", "info");

    try {
        const response = await fetch("/api/approve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                device_name: currentDeviceData.device_name,
                reviewer_name: reviewerName,
                reviewer_title: reviewerTitle,
                clinical_notes: clinicalNotes,
                draft_hash: currentDeviceData.draft_hash,
                legal_signature_intent: legalConfirm,
                password: password
            })
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.error || "Approval submission failed");
        }
        
        const data = await response.json();
        appendLog(`[+] Clinical clearance signed off by: ${reviewerName}`, "success");

        // Update stamp details
        document.getElementById("stamp-name").textContent = reviewerName;
        document.getElementById("stamp-title").textContent = reviewerTitle;
        document.getElementById("stamp-notes").textContent = clinicalNotes;
        
        // Show cryptographic audit hash and timestamp details
        document.getElementById("stamp-time").textContent = data.sign_off_timestamp.replace('T', ' ').slice(0, 19);
        document.getElementById("stamp-source").textContent = currentDeviceData.source;
        document.getElementById("stamp-hash").textContent = data.approved_hash;
        
        const cacheStatusText = currentDeviceData.cached ? "Local Archive Cache" : "Live Verification Connection";
        document.getElementById("stamp-cache-status").textContent = cacheStatusText;

        // Transition UI to Approved State
        statusBadge.className = "report-status-badge approved";
        statusBadge.innerHTML = `<i class="fa-solid fa-circle-check"></i> CLINICALLY APPROVED`;
        
        approvalForm.style.display = "none";
        signatureStamp.style.display = "flex";

    } catch (error) {
        appendLog(`[-] Failed to sign clinical clearance: ${error.message}`, "error");
        alert(`Failed to submit approval: ${error.message}`);
    }
}

// Crawl manufacturer websites and manuals to extract safety specifications
async function runAutoIngestion(query) {
    if (!query) return;
    
    const agentLog = document.getElementById("agent-log");
    const defaultView = document.getElementById("report-view-default");
    const activeView = document.getElementById("report-view-active");
    const addImplantView = document.getElementById("report-view-add-implant");
    const apiStatus = document.getElementById("api-status-badge");

    // Clear and reset UI views
    if (addImplantView) addImplantView.style.display = "none";
    defaultView.style.display = "flex";
    activeView.style.display = "none";
    agentLog.innerHTML = "";

    // Simulated log timeline for ingestion
    const logs = [
        { text: "⚙️ Initializing Web Auto-Ingestion Pipeline...", delay: 0, type: "info" },
        { text: `🔍 Target Device Query: "${query}"`, delay: 400, type: "info" },
        { text: "🌐 Searching DuckDuckGo for manufacturer sites and manuals...", delay: 1000, type: "info" },
        { text: "📄 Found specifications reference links, crawling manual pages...", delay: 1800, type: "info" },
        { text: "📥 Fetching and decoding page text content (excluding PDF binaries)...", delay: 2600, type: "info" },
        { text: "🧠 Parsing safety corpus using heuristic clinical rules...", delay: 3400, type: "warning" },
        { text: "💾 Writing auto-ingested safety sheet to registry database...", delay: 4200, type: "success" }
    ];

    logs.forEach(log => {
        setTimeout(() => {
            appendLog(log.text, log.type);
        }, log.delay);
    });

    // Make backend call after logging delays finish
    setTimeout(async () => {
        try {
            const response = await fetch("/api/ingest", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: query })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || "Ingestion request failed");
            }

            const data = await response.json();
            appendLog(`[+] Auto-Ingest Successful: '${query}' saved to registry.`, "success");
            
            // Set search input value and run standard verify to load report
            const searchInput = document.getElementById("search-input");
            if (searchInput) searchInput.value = query;
            
            // Automatically search and load the report
            runSafetyAgent(query);

        } catch (error) {
            appendLog(`[-] Ingestion failed: ${error.message}`, "error");
            alert(`Auto-Ingestion Failed: ${error.message}`);
        }
    }, 4600);
}

// Render Search Disambiguation Candidate List
function renderDisambiguation(data) {
    const defaultView = document.getElementById("report-view-default");
    const activeView = document.getElementById("report-view-active");
    const disambigView = document.getElementById("report-view-disambiguation");
    const titleQuery = document.getElementById("disambiguate-title-query");
    const listContainer = document.getElementById("disambiguation-list");

    if (!disambigView || !listContainer) return;

    // Set query title
    if (titleQuery) {
        titleQuery.textContent = `Matching Candidates for "${data.query}"`;
    }

    // Clear matches list
    listContainer.innerHTML = "";

    const matches = data.matches || [];
    const itemsPerPage = 10;
    let currentIndex = 0;

    // Create a container specifically for the cards
    const cardsContainer = document.createElement("div");
    cardsContainer.style.display = "flex";
    cardsContainer.style.flexDirection = "column";
    cardsContainer.style.gap = "12px";
    listContainer.appendChild(cardsContainer);

    // Create Load More button
    const loadMoreBtn = document.createElement("button");
    loadMoreBtn.className = "btn-load-more";
    loadMoreBtn.style.display = "none";
    listContainer.appendChild(loadMoreBtn);

    function renderNextChunk() {
        const chunk = matches.slice(currentIndex, currentIndex + itemsPerPage);
        chunk.forEach(match => {
            const card = document.createElement("div");
            card.className = "disambig-card";

            const textWrapper = document.createElement("div");
            textWrapper.style.display = "flex";
            textWrapper.style.flexDirection = "column";
            textWrapper.style.gap = "4px";

            const nameSpan = document.createElement("span");
            nameSpan.style.color = "#fff";
            nameSpan.style.fontSize = "14px";
            nameSpan.style.fontWeight = "600";
            nameSpan.textContent = match.name;

            const manSpan = document.createElement("span");
            manSpan.style.color = "var(--text-secondary)";
            manSpan.style.fontSize = "12px";
            manSpan.textContent = `Manufacturer: ${match.manufacturer}`;

            textWrapper.appendChild(nameSpan);
            textWrapper.appendChild(manSpan);

            const badge = document.createElement("span");
            badge.className = "suggestion-badge";
            if (match.source.toLowerCase().includes("mrisafety.com")) {
                badge.style.background = "rgba(59, 130, 246, 0.15)";
                badge.style.color = "var(--accent-blue)";
            } else {
                badge.classList.add("preset");
            }
            badge.textContent = match.source;

            if (match.link) {
                const viewLink = document.createElement("a");
                viewLink.href = match.link;
                viewLink.target = "_blank";
                viewLink.className = "disambig-link";
                viewLink.innerHTML = `<i class="fa-solid fa-arrow-up-right-from-square"></i> Inspect Crawled Manual`;
                viewLink.style.color = "var(--accent-blue)";
                viewLink.style.fontSize = "11.5px";
                viewLink.style.textDecoration = "none";
                viewLink.style.marginTop = "6px";
                viewLink.style.display = "inline-flex";
                viewLink.style.alignItems = "center";
                viewLink.style.gap = "4px";
                viewLink.style.fontWeight = "600";
                
                // Stop propagation to prevent selecting the card on link click
                viewLink.addEventListener("click", (e) => {
                    e.stopPropagation();
                });
                textWrapper.appendChild(viewLink);
            }

            card.appendChild(textWrapper);
            card.appendChild(badge);

            // Click Selection event listener
            card.addEventListener("click", () => {
                const searchInput = document.getElementById("search-input");
                if (searchInput) searchInput.value = match.name;
                runSafetyAgent(match.name);
            });

            cardsContainer.appendChild(card);
        });

        currentIndex += chunk.length;

        // Check if there are more items remaining
        if (currentIndex < matches.length) {
            const remaining = matches.length - currentIndex;
            loadMoreBtn.innerHTML = `<i class="fa-solid fa-arrow-down-long"></i> Load More Candidates (${remaining} remaining)`;
            loadMoreBtn.style.display = "flex";
        } else {
            loadMoreBtn.style.display = "none";
        }
    }

    // Set up click handler for load more
    loadMoreBtn.addEventListener("click", () => {
        renderNextChunk();
    });

    // Render first chunk
    renderNextChunk();

    // Toggle views
    defaultView.style.display = "none";
    activeView.style.display = "none";
    disambigView.style.display = "flex";
}

// Clinical Deletion Modal Controller & API Request
document.addEventListener("DOMContentLoaded", () => {
    const deleteBtn = document.getElementById("delete-listing-btn");
    const deleteModal = document.getElementById("delete-confirm-modal");
    const closeDeleteBtn = document.getElementById("close-delete-modal-btn");
    const deleteForm = document.getElementById("delete-signoff-form");
    const deviceDisplay = document.getElementById("delete-device-name-display");

    if (deleteBtn) {
        deleteBtn.addEventListener("click", () => {
            if (!currentDeviceData || !currentDeviceData.device_name) {
                alert("No active implant record is loaded to remove.");
                return;
            }
            if (deviceDisplay) {
                deviceDisplay.textContent = currentDeviceData.device_name;
            }
            // Clear inputs
            document.getElementById("delete-reviewer-name").value = "";
            document.getElementById("delete-reviewer-title").value = "";
            document.getElementById("delete-notes").value = "";
            document.getElementById("delete-legal-signature-intent").checked = false;
            document.getElementById("delete-password").value = "";
            
            // Show modal
            deleteModal.style.display = "flex";
        });
    }

    if (closeDeleteBtn) {
        closeDeleteBtn.addEventListener("click", () => {
            deleteModal.style.display = "none";
        });
    }

    if (deleteForm) {
        deleteForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            
            const reviewerName = document.getElementById("delete-reviewer-name").value.trim();
            const reviewerTitle = document.getElementById("delete-reviewer-title").value.trim();
            const clinicalNotes = document.getElementById("delete-notes").value.trim();
            const legalConfirm = document.getElementById("delete-legal-signature-intent").checked;
            const password = document.getElementById("delete-password").value.trim();

            if (!reviewerName || !reviewerTitle || !clinicalNotes) {
                alert("Signature parameters are incomplete.");
                return;
            }
            if (!password) {
                alert("E-signature password validation is required for removal.");
                return;
            }
            if (!legalConfirm) {
                alert("Electronic signature intent consent is required.");
                return;
            }

            appendLog(`[*] Requesting removal of implant: '${currentDeviceData.device_name}'...`, "warning");

            try {
                const response = await fetch("/api/remove", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        device_name: currentDeviceData.device_name,
                        reviewer_name: reviewerName,
                        reviewer_title: reviewerTitle,
                        clinical_notes: clinicalNotes,
                        legal_signature_intent: legalConfirm,
                        password: password
                    })
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.error || "Removal failed");
                }

                const data = await response.json();
                appendLog(`[+] Removal Signed: '${data.removed_device}' deleted from registry.`, "success");
                appendLog(`[+] Audit signature hash: ${data.removal_hash}`, "info");

                // Hide modal
                deleteModal.style.display = "none";
                alert(`Implant successfully removed.\nAudit Trail Hash: ${data.removal_hash}`);

                // Reset search bar and return to default view
                const searchInput = document.getElementById("search-input");
                if (searchInput) searchInput.value = "";
                
                document.getElementById("report-view-active").style.display = "none";
                document.getElementById("report-view-default").style.display = "flex";
                currentDeviceData = null;

            } catch (error) {
                appendLog(`[-] Removal request failed: ${error.message}`, "error");
                alert(`Removal Request Failed: ${error.message}`);
            }
        });
    }
});

