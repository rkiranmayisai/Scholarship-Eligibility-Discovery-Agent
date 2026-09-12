/* ============================================================
   ScholarAI frontend — vanilla JS SPA.
   Talks to the FastAPI backend (default http://localhost:8000).
   No build step required — open index.html or serve statically.
   ============================================================ */

const API_BASE = window.SCHOLARAI_API_BASE || "http://localhost:8000";

const state = {
  route: "landing",
  sessionId: null,
  result: null,          // last /api/discover response
  activeScholarshipId: null,
  chatHistory: [],
  profileMode: "text",   // 'text' | 'form'
  loggedIn: false,
  currentUserName: "Student",
  discoverData: [],
  discoverLoaded: false,
  discoverSelected: [],
  discoverSaved: [],
  discoverRemoved: [],
  discoverCompare: [],
  discoverFilters: {
    country: "All",
    course: "All",
    degree: "All",
    funding: "All",
    deadline: "All",
  },
};

const AGENT_SEQUENCE_ICONS = {
  "Profile Analyzer Agent": "🤖",
  "Discovery Agent": "🔎",
  "Eligibility Agent": "⚖️",
  "Ranking Agent": "📊",
  "Document Agent": "📄",
  "Deadline Agent": "⏰",
  "Planning Agent": "🧠",
};

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

function fmtMoney(v) {
  if (v === null || v === undefined) return "Not specified";
  return "₹" + Number(v).toLocaleString("en-IN");
}

function fmtDate(d) {
  if (!d) return "—";
  const dt = new Date(d);
  return dt.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

async function api(path, opts = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

/* ---------------- Routing / shell render ---------------- */
function setRoute(route) {
  state.route = route;
  render();
  if (route === "discover") {
    ensureDiscoverData().then(() => render());
  }
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
}

function render() {
  const app = document.getElementById("app");
  app.innerHTML = "";

  if (state.route === "landing") {
    app.appendChild(renderLanding());
    return;
  }

  // All non-landing routes use the app shell with topbar + optional agent rail
  const shell = el(`<div class="app-with-rail"></div>`);
  const left = el(`<div></div>`);
  left.appendChild(renderTopbar());
  left.appendChild(renderMainContent());
  shell.appendChild(left);
  shell.appendChild(renderAgentRail());
  app.appendChild(shell);
}

function renderTopbar() {
  const tabs = [
    { id: "profile", label: "Student Profile" },
    { id: "results", label: "Results" },
    { id: "discover", label: "Discover Opportunities" },
    { id: "documents", label: "Documents" },
    { id: "deadlines", label: "Deadlines" },
    { id: "plan", label: "Action Plan" },
    { id: "chat", label: "AI Chat" },
    { id: "login", label: state.loggedIn ? `${state.currentUserName}` : "Login" },
  ];
  const bar = el(`
    <div class="topbar">
      <div class="brand" style="cursor:pointer"><span class="mark"></span> ScholarAI</div>
      <div class="nav-tabs"></div>
    </div>
  `);
  bar.querySelector(".brand").onclick = () => setRoute("landing");
  const navTabs = bar.querySelector(".nav-tabs");
  tabs.forEach((t) => {
    const btn = el(`<button class="nav-tab ${state.route === t.id ? "active" : ""}">${t.label}</button>`);
    btn.onclick = () => setRoute(t.id);
    navTabs.appendChild(btn);
  });
  return bar;
}

function renderMainContent() {
  const wrap = el(`<div class="main"></div>`);
  switch (state.route) {
    case "profile": wrap.appendChild(renderProfilePage()); break;
    case "results": wrap.appendChild(renderResultsPage()); break;
    case "discover": wrap.appendChild(renderDiscoverPage()); break;
    case "documents": wrap.appendChild(renderDocumentsPage()); break;
    case "deadlines": wrap.appendChild(renderDeadlinesPage()); break;
    case "plan": wrap.appendChild(renderPlanPage()); break;
    case "chat": wrap.appendChild(renderChatPage()); break;
    case "login": wrap.appendChild(renderLoginPage()); break;
    default: wrap.appendChild(renderProfilePage());
  }
  return wrap;
}

/* ---------------- Agent Activity Rail ---------------- */
function renderAgentRail() {
  const rail = el(`
    <div class="agent-rail">
      <div class="rail-title">Agent Activity</div>
      <div id="agent-log-list"></div>
    </div>
  `);
  const list = rail.querySelector("#agent-log-list");
  const activity = state.result ? state.result.agent_activity : [];

  if (!activity.length) {
    list.appendChild(el(`
      <div class="empty-state" style="padding:32px 4px;">
        <div style="font-size:13px; color:var(--text-dim); line-height:1.6;">
          Submit your profile to watch the Profile, Discovery, Eligibility, Ranking,
          Document, Deadline and Planning agents work in sequence.
        </div>
      </div>
    `));
    return rail;
  }

  activity.forEach((a) => {
    list.appendChild(el(`
      <div class="agent-log-item">
        <div class="agent-log-icon">${a.icon}</div>
        <div>
          <div class="agent-log-name">${a.agent}</div>
          <div class="agent-log-msg">✓ ${a.message}</div>
        </div>
      </div>
    `));
  });
  return rail;
}

/* ---------------- Landing ---------------- */
function renderLanding() {
  const page = el(`<div></div>`);
  page.appendChild(renderTopbarLanding());
  const hero = el(`
    <div class="landing-hero">
      <div class="landing-grid">
        <div>
          <div class="eyebrow-line"><span class="rule"></span> Multi-agent scholarship discovery</div>
          <h1 class="display">Don't search for<br>scholarships. Let <em>AI find</em><br>the ones you qualify for.</h1>
          <p class="lede">
            Tell ScholarAI about yourself. Seven specialized agents — profile analysis,
            discovery, eligibility checking, ranking, documents, deadlines and planning —
            work together to explain exactly why you qualify, and prepare your application plan.
          </p>
          <div class="cta-row">
            <button class="btn btn-primary" id="cta-start">Find My Scholarships</button>
            <button class="btn btn-ghost" id="cta-discover">Discover Opportunities</button>
            <button class="btn btn-ghost" id="cta-chat">Ask the AI Assistant</button>
          </div>
          <div class="stat-strip">
            <div class="stat"><span class="num">22+</span><span class="label">scholarships in knowledge base</span></div>
            <div class="stat"><span class="num">7</span><span class="label">specialized agents</span></div>
            <div class="stat"><span class="num">3</span><span class="label">tiers: eligible, almost, not eligible</span></div>
          </div>
        </div>
        <div class="certificate-card">
          <div class="seal">AI<br>✓</div>
          <div style="font-size:12px; color:#8a7d5e; font-weight:600; letter-spacing:.04em;">SAMPLE MATCH</div>
          <h3>Telangana ePASS<br>Post-Matric Scholarship</h3>
          <div class="cert-row"><span class="k">Minimum CGPA</span><span class="v">— (not required)</span></div>
          <div class="cert-row"><span class="k">Max. family income</span><span class="v">₹3,00,000 ✓</span></div>
          <div class="cert-row"><span class="k">Domicile</span><span class="v">Telangana ✓</span></div>
          <div class="cert-row"><span class="k">Match score</span><span class="v" style="color:#8a6524">91%</span></div>
          <div style="margin-top:16px; font-size:12px; color:#8a7d5e;">Demo data — for illustration only.</div>
        </div>
      </div>

      <div class="workflow-strip">
        ${["Profile Analyzer", "Discovery Agent", "Eligibility Agent", "Ranking Agent", "Document Agent", "Deadline Agent", "Planning Agent"]
          .map((s, i, arr) => `<span class="workflow-chip">${s}</span>` + (i < arr.length - 1 ? `<span class="workflow-chip arrow">→</span>` : ""))
          .join("")}
      </div>
    </div>
  `);
  page.appendChild(hero);
  hero.querySelector("#cta-start").onclick = () => setRoute("profile");
  hero.querySelector("#cta-discover").onclick = () => setRoute("discover");
  hero.querySelector("#cta-chat").onclick = () => setRoute("chat");
  const loginBtn = el(`<button class="btn btn-ghost" id="cta-login">Login</button>`);
  loginBtn.onclick = () => setRoute("login");
  hero.querySelector(".cta-row").appendChild(loginBtn);
  return page;
}

function renderTopbarLanding() {
  const bar = el(`
    <div class="topbar">
      <div class="brand"><span class="mark"></span> ScholarAI</div>
      <div style="display:flex; gap:10px; align-items:center;">
        <button class="btn btn-ghost btn-sm" id="landing-login">Login</button>
        <button class="btn btn-primary btn-sm" id="landing-cta-2">Find My Scholarships</button>
      </div>
    </div>
  `);
  bar.querySelector("#landing-cta-2").onclick = () => setRoute("profile");
  bar.querySelector("#landing-login").onclick = () => setRoute("login");
  return bar;
}

/* ---------------- Student Profile Page ---------------- */
function renderProfilePage() {
  const wrap = el(`<div></div>`);
  wrap.appendChild(el(`
    <div>
      <div class="section-title">Tell us about yourself</div>
      <div class="section-sub">Describe your situation in your own words, or use the structured form. The Profile Analyzer Agent extracts what it needs and asks about anything important that's missing.</div>
    </div>
  `));

  const modeToggle = el(`
    <div class="mode-toggle">
      <button class="mode-btn ${state.profileMode === "text" ? "active" : ""}" data-mode="text">Natural language</button>
      <button class="mode-btn ${state.profileMode === "form" ? "active" : ""}" data-mode="form">Structured form</button>
    </div>
  `);
  modeToggle.querySelectorAll(".mode-btn").forEach((b) => {
    b.onclick = () => { state.profileMode = b.dataset.mode; render(); };
  });
  wrap.appendChild(modeToggle);

  const card = el(`<div class="card"></div>`);

  if (state.profileMode === "text") {
    card.appendChild(el(`
      <div class="field">
        <label>Describe yourself</label>
        <textarea id="profile-text" rows="5" placeholder="e.g. I am a third-year B.Tech CSE student from Telangana. My CGPA is 8.7 and my family income is 3 lakh per year.">I am a third-year B.Tech CSE student from Telangana. My CGPA is 8.7 and my family income is ₹3 lakh per year.</textarea>
      </div>
    `));
  } else {
    card.appendChild(el(`
      <div class="field-grid">
        <div class="field"><label>Course</label><input id="f-course" placeholder="B.Tech" /></div>
        <div class="field"><label>Branch</label><input id="f-branch" placeholder="CSE" /></div>
        <div class="field"><label>State / Domicile</label><input id="f-state" placeholder="Telangana" /></div>
        <div class="field"><label>Current year</label>
          <select id="f-year"><option value="">Select</option><option>1</option><option>2</option><option>3</option><option>4</option></select>
        </div>
        <div class="field"><label>CGPA</label><input id="f-cgpa" type="number" step="0.1" placeholder="8.7" /></div>
        <div class="field"><label>Family income (₹ / year)</label><input id="f-income" type="number" placeholder="300000" /></div>
        <div class="field"><label>Category</label>
          <select id="f-category"><option value="">Select</option><option>General</option><option>OBC</option><option>SC</option><option>ST</option><option>EWS</option><option>Minority</option><option>BC</option></select>
        </div>
        <div class="field"><label>Gender</label>
          <select id="f-gender"><option value="">Select</option><option>Male</option><option>Female</option><option>Other</option></select>
        </div>
        <div class="field"><label>Age</label><input id="f-age" type="number" placeholder="20" /></div>
        <div class="field"><label>Disability status</label>
          <select id="f-disability"><option value="">Select</option><option>No</option><option>Yes</option></select>
        </div>
      </div>
    `));
  }

  const submitRow = el(`
    <div>
      <button class="btn btn-primary" id="run-discovery">Run Scholarship Discovery →</button>
      <div id="discovery-status" style="margin-top:14px; font-size:13.5px; color:var(--text-mid);"></div>
    </div>
  `);
  card.appendChild(submitRow);
  wrap.appendChild(card);

  wrap.querySelector("#run-discovery").onclick = () => runDiscovery(wrap);

  if (state.result && state.result.follow_up_questions && state.result.follow_up_questions.length) {
    wrap.appendChild(el(`
      <div class="followups">
        <div class="ft-title">The Profile Agent needs a bit more information</div>
        <div style="font-size:13.5px; color:var(--text-hi);">${state.result.follow_up_questions.join(" · ")}</div>
      </div>
    `));
  }

  return wrap;
}

async function runDiscovery(wrap) {
  const statusEl = wrap.querySelector("#discovery-status");
  statusEl.textContent = "Running the agent pipeline — Profile → Discovery → Eligibility → Ranking → Documents → Deadlines → Plan...";

  const payload = { session_id: state.sessionId, documents_available: [] };

  if (state.profileMode === "text") {
    payload.raw_text = wrap.querySelector("#profile-text").value;
  } else {
    const val = (id) => wrap.querySelector(id)?.value || null;
    payload.structured = {
      course: val("#f-course"),
      branch: val("#f-branch"),
      state: val("#f-state"),
      current_year: val("#f-year"),
      cgpa: val("#f-cgpa") ? parseFloat(val("#f-cgpa")) : null,
      family_income: val("#f-income") ? parseFloat(val("#f-income")) : null,
      category: val("#f-category"),
      gender: val("#f-gender"),
      age: val("#f-age") ? parseInt(val("#f-age")) : null,
      disability_status: val("#f-disability"),
    };
  }

  try {
    const data = await api("/api/discover", { method: "POST", body: JSON.stringify(payload) });
    state.sessionId = data.session_id;
    state.result = data;
    statusEl.textContent = "Done. Redirecting to your results...";
    setTimeout(() => setRoute("results"), 300);
  } catch (err) {
    statusEl.innerHTML = `<span style="color:var(--red)">Could not reach the ScholarAI backend at ${API_BASE}. Make sure the FastAPI server is running (see README). Error: ${err.message}</span>`;
  }
}

/* ---------------- Results Page ---------------- */
function renderResultsPage() {
  const wrap = el(`<div></div>`);
  if (!state.result) {
    wrap.appendChild(emptyState("No results yet", "Fill in your profile to see your personalized scholarship matches.", "profile", "Go to Student Profile"));
    return wrap;
  }
  const r = state.result;

  wrap.appendChild(el(`
    <div>
      <div class="section-title">Your Scholarship Matches</div>
      <div class="section-sub">${r.ranked_scholarships.length} scholarships analyzed against your profile by the Eligibility and Ranking agents.</div>
    </div>
  `));

  wrap.appendChild(el(`
    <div class="summary-row">
      <div class="summary-pill eligible"><div class="n">${r.summary.ELIGIBLE}</div><div class="l">🟢 Eligible</div></div>
      <div class="summary-pill almost"><div class="n">${r.summary.ALMOST_ELIGIBLE}</div><div class="l">🟡 Almost Eligible</div></div>
      <div class="summary-pill not"><div class="n">${r.summary.NOT_ELIGIBLE}</div><div class="l">🔴 Not Eligible</div></div>
    </div>
  `));

  const list = el(`<div></div>`);
  r.ranked_scholarships.forEach((s, i) => {
    const badgeClass = s.eligibility_status === "ELIGIBLE" ? "badge-eligible" : s.eligibility_status === "ALMOST_ELIGIBLE" ? "badge-almost" : "badge-not";
    const badgeLabel = s.eligibility_status === "ELIGIBLE" ? "🟢 Eligible" : s.eligibility_status === "ALMOST_ELIGIBLE" ? "🟡 Needs Verification" : "🔴 Not Eligible";
    const medal = i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `${i + 1}.`;
    const card = el(`
      <div class="sch-card">
        <div class="sch-top">
          <div class="sch-rank">${medal}</div>
          <div style="flex:1">
            <div class="sch-name">${s.scholarship_name}</div>
            <div class="sch-provider">${s.provider}</div>
          </div>
          <div style="text-align:right">
            <div class="match-score">${s.match_score}%</div>
            <span class="badge ${badgeClass}">${badgeLabel}</span>
          </div>
        </div>
        <div class="sch-meta">
          <span>💰 ${fmtMoney(s.scholarship_amount)}</span>
          <span>📅 ${fmtDate(s.application_deadline)} ${s.days_remaining !== null ? `(${s.days_remaining}d left)` : ""}</span>
          <span class="source-tag ${sourceTagClass(s)}">${s.source_type}</span>
        </div>
      </div>
    `);
    card.onclick = () => openEligibilityModal(s.scholarship_id);
    list.appendChild(card);
  });
  wrap.appendChild(list);

  wrap.appendChild(el(`
    <div class="disclaimer">
      Match scores and eligibility statuses are generated from the demo scholarship knowledge base and your stated profile.
      Scholarship rules change — always confirm requirements and deadlines on the official application portal before applying.
    </div>
  `));

  return wrap;
}

function sourceTagClass(s) {
  const vs = (s.verification_status || "").toUpperCase();
  if (vs === "VERIFIED") return "verified";
  if (vs === "NEEDS_VERIFICATION") return "needs-verification";
  if (vs === "EXPIRED") return "expired";
  return "";
}

function emptyState(title, sub, routeId, ctaLabel) {
  const e = el(`
    <div class="empty-state">
      <div class="big">${title}</div>
      <div>${sub}</div>
      <div style="margin-top:20px;"><button class="btn btn-primary btn-sm" id="empty-cta">${ctaLabel}</button></div>
    </div>
  `);
  e.querySelector("#empty-cta").onclick = () => setRoute(routeId);
  return e;
}

/* ---------------- Eligibility Modal ---------------- */
function openEligibilityModal(scholarshipId) {
  const elig = state.result.eligibility_details[scholarshipId];
  const sch = state.result.ranked_scholarships.find((s) => s.scholarship_id === scholarshipId);
  if (!elig) return;

  const backdrop = el(`<div class="modal-backdrop"></div>`);
  const modal = el(`
    <div class="modal">
      <button class="modal-close" id="modal-close">×</button>
      <div style="font-size:12px; color:var(--text-dim); font-family:var(--mono); margin-bottom:6px;">WHY YOU ${elig.status === "NOT_ELIGIBLE" ? "DON'T" : "DO"} QUALIFY</div>
      <h3 style="font-family:var(--serif); font-size:22px; margin:0 0 4px;">${elig.scholarship_name}</h3>
      <div style="color:var(--text-mid); font-size:14px; margin-bottom:8px;">${sch ? sch.provider : ""}</div>
      <span class="badge ${elig.status === "ELIGIBLE" ? "badge-eligible" : elig.status === "ALMOST_ELIGIBLE" ? "badge-almost" : "badge-not"}">
        ${elig.status === "ELIGIBLE" ? "🟢 Eligible" : elig.status === "ALMOST_ELIGIBLE" ? "🟡 Almost Eligible / Needs Verification" : "🔴 Not Eligible"}
      </span>
      <div style="margin:8px 0 18px; font-size:13.5px; color:var(--text-mid);">
        Passed ${elig.passed_count} of ${elig.total_count} checked requirements · Confidence: ${elig.confidence}
      </div>
      ${elig.status === "ALMOST_ELIGIBLE" && elig.missing_requirement_summary ? `
        <div class="followups" style="margin-bottom:18px;">
          <div class="ft-title">You satisfy ${elig.passed_count} of ${elig.total_count} requirements</div>
          <div style="font-size:13.5px;">${elig.missing_requirement_summary}</div>
        </div>` : ""}
      <div id="req-list"></div>
      <div class="disclaimer">Source: demo scholarship knowledge base. Confirm current requirements on the official portal before applying.</div>
    </div>
  `);
  const reqList = modal.querySelector("#req-list");
  elig.checks.forEach((c) => {
    const cls = c.result === "PASS" ? "check-pass" : c.result === "FAIL" ? "check-fail" : "check-unknown";
    const icon = c.result === "PASS" ? "✓" : c.result === "FAIL" ? "✗" : "?";
    reqList.appendChild(el(`
      <div class="req-row">
        <div class="req-top"><span>${c.requirement}</span><span class="${cls}">${icon} ${c.result}</span></div>
        <div class="req-values"><span>Required: ${c.required_value}</span><span>Yours: ${c.student_value}</span></div>
        <div class="req-explain">${c.explanation}</div>
      </div>
    `));
  });

  backdrop.appendChild(modal);
  backdrop.onclick = (e) => { if (e.target === backdrop) document.body.removeChild(backdrop); };
  modal.querySelector("#modal-close").onclick = () => document.body.removeChild(backdrop);

  if (sch && sch.evidence && sch.evidence.length) {
    const evBlock = el(`<div class="evidence-block"><div class="evidence-title">Evidence from source</div></div>`);
    sch.evidence.slice(0, 8).forEach((ev) => {
      evBlock.appendChild(el(`
        <div class="evidence-item">
          <span class="ev-field">${ev.field}</span>: ${ev.value}
          <span class="ev-quote">"${ev.evidence}"</span>
          ${ev.source_url ? `<span class="ev-link">Source: ${ev.source_url}</span>` : ""}
        </div>
      `));
    });
    modal.appendChild(evBlock);
  }
  if (sch && sch.secondary_sources && sch.secondary_sources.length) {
    modal.appendChild(el(`
      <div class="disclaimer">Also found on: ${sch.secondary_sources.join(", ")}</div>
    `));
  }

  document.body.appendChild(backdrop);
}

/* ---------------- Documents Page ---------------- */
function renderDocumentsPage() {
  const wrap = el(`<div></div>`);
  if (!state.result) {
    wrap.appendChild(emptyState("No document checklist yet", "Run a scholarship search first to generate your personalized document checklist.", "profile", "Go to Student Profile"));
    return wrap;
  }
  const r = state.result;

  wrap.appendChild(el(`
    <div>
      <div class="section-title">Document Checklist</div>
      <div class="section-sub">Generated by the Document Agent across all your eligible and almost-eligible scholarships.</div>
    </div>
  `));

  const masterCard = el(`<div class="card"><h3 style="font-family:var(--serif); margin-top:0;">Master Checklist</h3><div id="master-list"></div></div>`);
  const masterList = masterCard.querySelector("#master-list");
  r.master_checklist.forEach((doc) => {
    masterList.appendChild(el(`
      <div class="doc-item">
        <div class="doc-checkbox">☐</div>
        <div class="doc-name">${doc}</div>
      </div>
    `));
  });
  wrap.appendChild(masterCard);

  r.document_checklists.forEach((chk) => {
    const card = el(`<div class="card"><h3 style="font-family:var(--serif); font-size:17px; margin-top:0;">${chk.scholarship_name}</h3><div class="doc-checklist-body"></div></div>`);
    const body = card.querySelector(".doc-checklist-body");
    chk.documents.forEach((doc) => {
      const item = el(`
        <div class="doc-item">
          <div class="doc-checkbox ${doc.status === "Available" ? "checked" : ""}">${doc.status === "Available" ? "✓" : "☐"}</div>
          <div class="doc-name">${doc.document}</div>
          <div class="doc-status">${doc.status}</div>
        </div>
      `);
      item.querySelector(".doc-checkbox").onclick = async () => {
        const newStatus = doc.status === "Available" ? "Missing" : "Available";
        doc.status = newStatus;
        try {
          await api("/api/documents/update", {
            method: "POST",
            body: JSON.stringify({ session_id: state.sessionId, scholarship_id: chk.scholarship_id, document: doc.document, status: newStatus }),
          });
        } catch (e) { /* local state already updated for demo continuity */ }
        render();
      };
      body.appendChild(item);
    });
    wrap.appendChild(card);
  });

  return wrap;
}

/* ---------------- Deadlines Page ---------------- */
function renderDeadlinesPage() {
  const wrap = el(`<div></div>`);
  if (!state.result) {
    wrap.appendChild(emptyState("No deadlines yet", "Run a scholarship search first to see your prioritized deadline tracker.", "profile", "Go to Student Profile"));
    return wrap;
  }
  const r = state.result;
  wrap.appendChild(el(`
    <div>
      <div class="section-title">Deadline Tracker</div>
      <div class="section-sub">Prioritized by the Deadline Agent based on days remaining.</div>
    </div>
  `));

  const groups = [
    { key: "Urgent", label: "🔴 Urgent Applications", color: "var(--red)" },
    { key: "Apply Soon", label: "🟠 Applications To Prepare", color: "var(--amber)" },
    { key: "Later", label: "🟢 Upcoming", color: "var(--green)" },
  ];

  groups.forEach((g) => {
    const items = r.deadlines.filter((d) => d.priority === g.key);
    if (!items.length) return;
    const groupEl = el(`<div class="deadline-group"><div class="deadline-group-title" style="color:${g.color}">${g.label}</div></div>`);
    items.forEach((d) => {
      groupEl.appendChild(el(`
        <div class="deadline-item">
          <div>
            <div style="font-weight:600; font-size:14.5px;">${d.scholarship_name}</div>
            <div style="font-size:12.5px; color:var(--text-dim);">Deadline: ${fmtDate(d.deadline)}</div>
          </div>
          <div class="deadline-days" style="color:${g.color}">${d.days_remaining}d</div>
        </div>
      `));
    });
    wrap.appendChild(groupEl);
  });

  if (!r.deadlines.length) {
    wrap.appendChild(el(`<div class="card">No active deadlines among your actionable scholarships right now.</div>`));
  }

  return wrap;
}

/* ---------------- Action Plan Page ---------------- */
function renderPlanPage() {
  const wrap = el(`<div></div>`);
  if (!state.result) {
    wrap.appendChild(emptyState("No action plan yet", "Run a scholarship search first to generate your personalized application plan.", "profile", "Go to Student Profile"));
    return wrap;
  }
  const r = state.result;
  wrap.appendChild(el(`
    <div>
      <div class="section-title">Your Scholarship Action Plan</div>
      <div class="section-sub">Built by the Planning Agent from your documents, deadlines, and eligibility results.</div>
    </div>
  `));

  const card = el(`<div class="card"></div>`);
  r.action_plan.forEach((day) => {
    const dayEl = el(`
      <div class="plan-day">
        <div class="plan-day-num">${day.day}</div>
        <div class="plan-tasks"></div>
      </div>
    `);
    const tasksEl = dayEl.querySelector(".plan-tasks");
    day.tasks.forEach((t) => tasksEl.appendChild(el(`<div class="plan-task">• ${t}</div>`)));
    card.appendChild(dayEl);
  });
  wrap.appendChild(card);
  return wrap;
}

/* ---------------- Chat Page ---------------- */
function renderLoginPage() {
  const wrap = el(`<div class="auth-page"></div>`);

  const card = el(`
    <div class="auth-card">
      <div class="auth-header">
        <div class="section-title" style="margin-bottom:4px;">Welcome back</div>
        <div class="section-sub">Sign in to continue with ScholarAI.</div>
      </div>
      <form id="login-form" class="auth-form">
        <div class="field">
          <label>Email</label>
          <input id="login-email" type="email" placeholder="student@example.com" required />
        </div>
        <div class="field">
          <label>Password</label>
          <input id="login-password" type="password" placeholder="Enter your password" required />
        </div>
        <button class="btn btn-primary" type="submit">Login</button>
      </form>
      <div class="auth-footer">
        <div>Demo access: use any email and password.</div>
        <button class="btn btn-ghost btn-sm" id="login-guest">Continue as guest</button>
      </div>
    </div>
  `);

  wrap.appendChild(card);

  card.querySelector("#login-form").onsubmit = (event) => {
    event.preventDefault();
    const email = card.querySelector("#login-email").value.trim();
    const password = card.querySelector("#login-password").value.trim();

    if (!email || !password) return;

    state.loggedIn = true;
    state.currentUserName = email.split("@")[0] || "Student";
    setRoute("profile");
  };

  card.querySelector("#login-guest").onclick = () => {
    state.loggedIn = false;
    state.currentUserName = "Student";
    setRoute("profile");
  };

  return wrap;
}

function renderChatPage() {
  const wrap = el(`<div></div>`);
  wrap.appendChild(el(`
    <div>
      <div class="section-title">AI Scholarship Assistant</div>
      <div class="section-sub">Ask about eligibility, documents, or what to prioritize. Answers are grounded in your actual agent results.</div>
    </div>
  `));

  const chatWindow = el(`
    <div class="chat-window">
      <div class="chat-messages" id="chat-messages"></div>
      <div class="chat-input-row">
        <input id="chat-input" placeholder="e.g. Which scholarship should I apply for first?" />
        <button class="btn btn-primary btn-sm" id="chat-send">Send</button>
      </div>
    </div>
  `);
  wrap.appendChild(chatWindow);

  const messagesEl = chatWindow.querySelector("#chat-messages");
  const renderMessages = () => {
    messagesEl.innerHTML = "";
    if (!state.chatHistory.length) {
      messagesEl.appendChild(el(`<div class="chat-bubble bot">Hi! I can answer questions about your scholarship matches — eligibility, required documents, or which application to prioritize. ${state.result ? "" : "Run a scholarship search first so I have your results to work from."}</div>`));
    }
    state.chatHistory.forEach((m) => {
      messagesEl.appendChild(el(`<div class="chat-bubble ${m.role}">${m.text}</div>`));
    });
    messagesEl.scrollTop = messagesEl.scrollHeight;
  };
  renderMessages();

  const send = async () => {
    const input = chatWindow.querySelector("#chat-input");
    const msg = input.value.trim();
    if (!msg) return;
    state.chatHistory.push({ role: "user", text: msg });
    input.value = "";
    renderMessages();
    try {
      const data = await api("/api/chat", { method: "POST", body: JSON.stringify({ session_id: state.sessionId || "no-session", message: msg }) });
      state.chatHistory.push({ role: "bot", text: data.reply });
    } catch (e) {
      state.chatHistory.push({ role: "bot", text: `Could not reach the backend at ${API_BASE}. Make sure the FastAPI server is running.` });
    }
    renderMessages();
  };
  chatWindow.querySelector("#chat-send").onclick = send;
  chatWindow.querySelector("#chat-input").addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });

  return wrap;
}

/* ---------------- Discover Opportunities Page ---------------- */
async function ensureDiscoverData() {
  if (state.discoverLoaded || state.discoverData.length) return;
  try {
    const data = await api("/api/scholarships");
    state.discoverData = data;
    state.discoverLoaded = true;
    if (!state.discoverSelected.length && state.result?.ranked_scholarships?.length) {
      state.discoverSelected = state.result.ranked_scholarships.slice(0, 3).map((s) => s.scholarship_id);
    }
  } catch (error) {
    state.discoverError = error.message;
  }
}

function getProfileSnapshot() {
  const profile = state.result?.profile || {};
  return {
    course: profile.course || "",
    branch: profile.branch || "",
    state: profile.state || profile.domicile || "",
    category: profile.category || "",
    gender: profile.gender || "",
    year: profile.current_year || "",
    degree: profile.current_year ? (profile.current_year >= 3 ? "Undergraduate" : "Undergraduate") : "Undergraduate",
  };
}

function getDegreeLevel(scholarship) {
  const text = (scholarship.eligible_courses || []).join(" ").toLowerCase();
  if (text.includes("pg") || text.includes("postgraduate")) return "Postgraduate";
  if (text.includes("ug") || text.includes("undergraduate")) return "Undergraduate";
  if (text.includes("diploma")) return "Diploma";
  return "Mixed";
}

function getFundingType(scholarship) {
  if ((scholarship.scholarship_amount || 0) >= 50000) return "Fully Funded";
  return "Partially Funded";
}

function getDeadlineMeta(scholarship) {
  if (!scholarship.application_deadline) {
    return { status: "Open", daysRemaining: null, deadline: null };
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const deadline = new Date(scholarship.application_deadline + "T00:00:00");
  const diffDays = Math.ceil((deadline - today) / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return { status: "Closed", daysRemaining: diffDays, deadline };
  if (diffDays <= 14) return { status: "Closing Soon", daysRemaining: diffDays, deadline };
  return { status: "Open", daysRemaining: diffDays, deadline };
}

function getTrustedPortal(scholarship) {
  if (!scholarship.official_url) return { isTrusted: false, label: "No official link" };
  const domain = new URL(scholarship.official_url).hostname.replace("www.", "");
  const trustedDomains = ["gov.in", "aicte", "ugc", "reliancefoundation", "google", "jntataendowment", "cgg.gov.in"];
  const isTrusted = trustedDomains.some((part) => domain.includes(part));
  return { isTrusted, label: isTrusted ? "Official portal" : "External source" };
}

function getFilteredScholarships() {
  const filters = state.discoverFilters;
  return state.discoverData.filter((scholarship) => {
    const eligibleStates = scholarship.eligible_states || [];
    const eligibleCourses = scholarship.eligible_courses || [];

    if (filters.country !== "All" && !eligibleStates.some((s) => s.toLowerCase() === filters.country.toLowerCase())) {
      return false;
    }

    if (filters.course !== "All") {
      const courseMatch = eligibleCourses.some((course) => {
        const courseText = course.toLowerCase();
        return courseText.includes(filters.course.toLowerCase()) || filters.course.toLowerCase().includes(courseText);
      });
      if (!courseMatch) return false;
    }

    if (filters.degree !== "All" && getDegreeLevel(scholarship) !== filters.degree) {
      return false;
    }

    if (filters.funding !== "All" && getFundingType(scholarship) !== filters.funding) {
      return false;
    }

    if (filters.deadline !== "All" && getDeadlineMeta(scholarship).status !== filters.deadline) {
      return false;
    }

    return true;
  });
}

function getDiscoverRecommendations() {
  const profile = getProfileSnapshot();
  const selected = state.discoverData.filter((scholarship) => state.discoverSelected.includes(scholarship.id));
  const saved = state.discoverData.filter((scholarship) => state.discoverSaved.includes(scholarship.id));

  const candidates = state.discoverData.filter((scholarship) => {
    const inRemoved = state.discoverRemoved.includes(scholarship.id);
    const inSelected = state.discoverSelected.includes(scholarship.id);
    return !inRemoved && !inSelected;
  });

  const recommendationList = candidates.map((scholarship) => {
    let score = 0;
    const reasons = [];

    const trusted = getTrustedPortal(scholarship);
    if (trusted.isTrusted) {
      score += 18;
      reasons.push("Official portal available");
    }

    if (profile.course) {
      const courseOverlap = (scholarship.eligible_courses || []).some((course) => {
        const text = course.toLowerCase();
        return text.includes(profile.course.toLowerCase()) || profile.course.toLowerCase().includes(text) || text.includes("any");
      });
      if (courseOverlap) {
        score += 20;
        reasons.push("Strong course fit");
      } else {
        score += 4;
      }
    }

    if (profile.state) {
      const stateMatch = (scholarship.eligible_states || []).some((country) => {
        const countryText = country.toLowerCase();
        return countryText.includes("all india") || countryText.includes(profile.state.toLowerCase());
      });
      if (stateMatch) {
        score += 12;
        reasons.push("Matches your location preference");
      }
    }

    if (profile.category) {
      const categoryMatch = (scholarship.category_conditions || []).some((category) => category.toLowerCase() === profile.category.toLowerCase());
      if (categoryMatch) {
        score += 10;
        reasons.push("Matches your category");
      }
    }

    if (profile.gender) {
      const genderMatch = scholarship.gender_conditions && scholarship.gender_conditions.toLowerCase() !== "any"
        ? scholarship.gender_conditions.toLowerCase() === profile.gender.toLowerCase()
        : true;
      if (genderMatch) {
        score += 6;
      }
    }

    if (saved.length) {
      const savedOverlap = saved.reduce((acc, s) => {
        let overlap = 0;
        if ((s.eligible_courses || []).some((c) => (scholarship.eligible_courses || []).includes(c))) overlap += 1;
        if ((s.eligible_states || []).some((c) => (scholarship.eligible_states || []).includes(c))) overlap += 1;
        if ((s.category_conditions || []).some((c) => (scholarship.category_conditions || []).includes(c))) overlap += 1;
        return acc + overlap;
      }, 0);
      if (savedOverlap) {
        score += savedOverlap * 8;
        reasons.push("Aligned with your saved opportunities");
      }
    }

    const deadlineMeta = getDeadlineMeta(scholarship);
    if (deadlineMeta.status === "Open") {
      score += 8;
    } else if (deadlineMeta.status === "Closing Soon") {
      score += 3;
    } else {
      score -= 25;
    }

    if (scholarship.scholarship_amount) {
      score += Math.min(10, scholarship.scholarship_amount / 20000);
    }

    if (selected.length) {
      const selectedOverlap = selected.reduce((acc, s) => {
        let overlap = 0;
        if ((s.eligible_courses || []).some((c) => (scholarship.eligible_courses || []).includes(c))) overlap += 1;
        if ((s.eligible_states || []).some((c) => (scholarship.eligible_states || []).includes(c))) overlap += 1;
        if ((s.category_conditions || []).some((c) => (scholarship.category_conditions || []).includes(c))) overlap += 1;
        return acc + overlap;
      }, 0);
      if (selectedOverlap) {
        score += selectedOverlap * 5;
      }
    }

    return {
      scholarship,
      score: Math.max(0, Math.round(score)),
      reason: reasons.length ? reasons[0] : "Recommended based on your preferences",
      deadlineMeta,
    };
  });

  return recommendationList.sort((a, b) => b.score - a.score).slice(0, 8);
}

function renderDiscoverPage() {
  const wrap = el(`<div></div>`);

  if (!state.discoverLoaded) {
    wrap.appendChild(el(`
      <div class="card">
        <div class="section-title">Discover Opportunities</div>
        <div class="section-sub">Loading the scholarship catalog and recommendations...</div>
      </div>
    `));
    return wrap;
  }

  const filteredScholarships = getFilteredScholarships();
  const recommendations = getDiscoverRecommendations();
  const selectedCount = state.discoverSelected.length;
  const compareCount = state.discoverCompare.length;

  wrap.appendChild(el(`
    <div class="discover-header">
      <div>
        <div class="section-title">Discover Opportunities</div>
        <div class="section-sub">Explore trusted scholarships, apply filters, bookmark opportunities, and compare the ones you care about.</div>
      </div>
      <div class="discover-header-actions">
        <button class="btn btn-ghost" id="discover-reset">Reset selection</button>
      </div>
    </div>
  `));

  const filterCard = el(`
    <div class="card discover-filters-card">
      <div class="discover-topline">Filters</div>
      <div class="filter-row">
        <div class="field">
          <label>Country</label>
          <select id="discover-country"></select>
        </div>
        <div class="field">
          <label>Course / Field</label>
          <select id="discover-course"></select>
        </div>
        <div class="field">
          <label>Degree level</label>
          <select id="discover-degree"></select>
        </div>
        <div class="field">
          <label>Funding type</label>
          <select id="discover-funding"></select>
        </div>
        <div class="field">
          <label>Deadline</label>
          <select id="discover-deadline"></select>
        </div>
      </div>
    </div>
  `);

  const countryOptions = ["All", ...new Set((state.discoverData || []).flatMap((s) => s.eligible_states || []))];
  const courseOptions = ["All", ...new Set((state.discoverData || []).flatMap((s) => s.eligible_courses || []))];
  const degreeOptions = ["All", ...new Set((state.discoverData || []).map((s) => getDegreeLevel(s)))];
  const fundingOptions = ["All", "Fully Funded", "Partially Funded"];
  const deadlineOptions = ["All", "Open", "Closing Soon", "Closed"];

  const setSelectOptions = (select, options, value) => {
    select.innerHTML = options.map((option) => `<option value="${option}">${option}</option>`).join("");
    select.value = value;
  };

  const countrySelect = filterCard.querySelector("#discover-country");
  const courseSelect = filterCard.querySelector("#discover-course");
  const degreeSelect = filterCard.querySelector("#discover-degree");
  const fundingSelect = filterCard.querySelector("#discover-funding");
  const deadlineSelect = filterCard.querySelector("#discover-deadline");

  setSelectOptions(countrySelect, countryOptions, state.discoverFilters.country);
  setSelectOptions(courseSelect, courseOptions, state.discoverFilters.course);
  setSelectOptions(degreeSelect, degreeOptions, state.discoverFilters.degree);
  setSelectOptions(fundingSelect, fundingOptions, state.discoverFilters.funding);
  setSelectOptions(deadlineSelect, deadlineOptions, state.discoverFilters.deadline);

  countrySelect.onchange = (e) => { state.discoverFilters.country = e.target.value; render(); };
  courseSelect.onchange = (e) => { state.discoverFilters.course = e.target.value; render(); };
  degreeSelect.onchange = (e) => { state.discoverFilters.degree = e.target.value; render(); };
  fundingSelect.onchange = (e) => { state.discoverFilters.funding = e.target.value; render(); };
  deadlineSelect.onchange = (e) => { state.discoverFilters.deadline = e.target.value; render(); };

  wrap.appendChild(filterCard);

  const topStats = el(`
    <div class="summary-row discover-summary">
      <div class="summary-pill eligible"><div class="n">${selectedCount}</div><div class="l">Selected</div></div>
      <div class="summary-pill almost"><div class="n">${recommendations.length}</div><div class="l">AI recommendations</div></div>
      <div class="summary-pill not"><div class="n">${compareCount}</div><div class="l">Compare queue</div></div>
    </div>
  `);
  wrap.appendChild(topStats);

  const comparePanel = el(`<div class="compare-panel"></div>`);
  if (state.discoverCompare.length) {
    const compareCountEl = el(`<div class="compare-card-header">Compare list</div>`);
    const compareList = el(`<div class="compare-list"></div>`);
    comparePanel.appendChild(compareCountEl);
    state.discoverCompare.forEach((id) => {
      const scholarship = state.discoverData.find((s) => s.id === id);
      if (!scholarship) return;
      const deadlineMeta = getDeadlineMeta(scholarship);
      compareList.appendChild(el(`
        <div class="compare-card">
          <div class="compare-title">${scholarship.name}</div>
          <div class="compare-meta">${scholarship.provider}</div>
          <div class="compare-meta">${fmtMoney(scholarship.scholarship_amount)} · ${deadlineMeta.status}</div>
        </div>
      `));
    });
    comparePanel.appendChild(compareList);
    wrap.appendChild(comparePanel);
  }

  const catalogWrap = el(`<div class="discover-grid"></div>`);
  filteredScholarships.forEach((scholarship) => {
    const selected = state.discoverSelected.includes(scholarship.id);
    const saved = state.discoverSaved.includes(scholarship.id);
    const compareActive = state.discoverCompare.includes(scholarship.id);
    const deadlineMeta = getDeadlineMeta(scholarship);
    const portalInfo = getTrustedPortal(scholarship);
    const fundingType = getFundingType(scholarship);
    const statusClass = deadlineMeta.status === "Closed" ? "badge-closed" : deadlineMeta.status === "Closing Soon" ? "badge-closing" : "badge-open";
    const portalBtn = portalInfo.isTrusted
      ? `<a class="mini-btn portal-btn" href="${scholarship.official_url}" target="_blank" rel="noopener noreferrer">Visit Scholarship Portal</a>`
      : `<button class="mini-btn disabled" disabled>Official link unavailable</button>`;

    const card = el(`
      <div class="discover-card">
        <div class="discover-card-header">
          <div>
            <div class="discover-card-title">${scholarship.name}</div>
            <div class="muted">${scholarship.provider}</div>
          </div>
          <label class="select-toggle">
            <input type="checkbox" ${selected ? "checked" : ""} />
          </label>
        </div>
        <div class="discover-badges">
          <span class="badge ${statusClass}">${deadlineMeta.status}</span>
          <span class="badge badge-neutral">${fundingType}</span>
          <span class="badge badge-neutral">${portalInfo.label}</span>
        </div>
        <div class="discover-description">${scholarship.description}</div>
        <div class="discover-meta-grid">
          <div><span class="meta-label">Eligibility</span><span>${(scholarship.category_conditions || []).join(", ") || "Open"}</span></div>
          <div><span class="meta-label">Course / Field</span><span>${(scholarship.eligible_courses || []).join(", ")}</span></div>
          <div><span class="meta-label">Country</span><span>${(scholarship.eligible_states || []).join(", ")}</span></div>
          <div><span class="meta-label">Department / Org</span><span>${scholarship.provider}</span></div>
          <div><span class="meta-label">Deadline</span><span>${deadlineMeta.daysRemaining !== null ? `${deadlineMeta.daysRemaining} days left` : "Not specified"}</span></div>
          <div><span class="meta-label">Amount</span><span>${fmtMoney(scholarship.scholarship_amount)}</span></div>
        </div>
        <div class="discover-actions">
          ${portalBtn}
          <button class="mini-btn ${saved ? "active" : ""}" data-save="${scholarship.id}">${saved ? "Bookmarked" : "Save"}</button>
          <button class="mini-btn ${compareActive ? "active" : ""}" data-compare="${scholarship.id}">${compareActive ? "Comparing" : "Compare"}</button>
          <button class="mini-btn danger" data-remove="${scholarship.id}">Remove</button>
        </div>
      </div>
    `);

    const checkbox = card.querySelector('input[type="checkbox"]');
    checkbox.onchange = () => {
      if (checkbox.checked) {
        state.discoverSelected = [...new Set([...state.discoverSelected, scholarship.id])];
      } else {
        state.discoverSelected = state.discoverSelected.filter((id) => id !== scholarship.id);
      }
      render();
    };

    const saveButton = card.querySelector('[data-save]');
    saveButton.onclick = () => {
      if (state.discoverSaved.includes(scholarship.id)) {
        state.discoverSaved = state.discoverSaved.filter((id) => id !== scholarship.id);
      } else {
        state.discoverSaved = [...new Set([...state.discoverSaved, scholarship.id])];
      }
      render();
    };

    const compareButton = card.querySelector('[data-compare]');
    compareButton.onclick = () => {
      if (state.discoverCompare.includes(scholarship.id)) {
        state.discoverCompare = state.discoverCompare.filter((id) => id !== scholarship.id);
      } else {
        state.discoverCompare = [...new Set([...state.discoverCompare, scholarship.id])].slice(0, 3);
      }
      render();
    };

    const removeButton = card.querySelector('[data-remove]');
    removeButton.onclick = () => {
      state.discoverRemoved = [...new Set([...state.discoverRemoved, scholarship.id])];
      state.discoverSelected = state.discoverSelected.filter((id) => id !== scholarship.id);
      state.discoverCompare = state.discoverCompare.filter((id) => id !== scholarship.id);
      state.discoverSaved = state.discoverSaved.filter((id) => id !== scholarship.id);
      render();
    };

    catalogWrap.appendChild(card);
  });

  wrap.appendChild(catalogWrap);

  const recommendationsWrap = el(`<div class="recommendations-section"></div>`);
  recommendationsWrap.appendChild(el(`<div class="section-title" style="margin-top:24px;">AI Recommended Scholarships</div>`));

  const recommendationCards = el(`<div class="discover-grid"></div>`);
  if (!recommendations.length) {
    recommendationCards.appendChild(el(`
      <div class="card empty-state tiny">
        <div class="big">No recommendations yet</div>
        <div>Select one or more scholarships from the catalog to generate new suggestions.</div>
      </div>
    `));
  } else {
    recommendations.forEach(({ scholarship, score, reason, deadlineMeta }) => {
      const trusted = getTrustedPortal(scholarship);
      recommendationCards.appendChild(el(`
        <div class="discover-card recommendation-card">
          <div class="discover-card-header">
            <div>
              <div class="discover-card-title">${scholarship.name}</div>
              <div class="muted">${scholarship.provider}</div>
            </div>
            <div class="score-pill">${score}% match</div>
          </div>
          <div class="discover-badges">
            <span class="badge ${deadlineMeta.status === "Closed" ? "badge-closed" : deadlineMeta.status === "Closing Soon" ? "badge-closing" : "badge-open"}">${deadlineMeta.status}</span>
            <span class="badge badge-neutral">${getFundingType(scholarship)}</span>
            <span class="badge badge-neutral">${trusted.label}</span>
          </div>
          <div class="discover-description">${scholarship.description}</div>
          <div class="recommendation-reason">Why this fits: ${reason}</div>
          <div class="discover-meta-grid compact">
            <div><span class="meta-label">Eligibility</span><span>${(scholarship.category_conditions || []).join(", ") || "Open"}</span></div>
            <div><span class="meta-label">Deadline</span><span>${deadlineMeta.daysRemaining !== null ? `${deadlineMeta.daysRemaining} days left` : "Not specified"}</span></div>
            <div><span class="meta-label">Amount</span><span>${fmtMoney(scholarship.scholarship_amount)}</span></div>
            <div><span class="meta-label">Country</span><span>${(scholarship.eligible_states || []).join(", ")}</span></div>
          </div>
          <div class="discover-actions">
            <a class="mini-btn portal-btn" href="${scholarship.official_url}" target="_blank" rel="noopener noreferrer">Apply Now</a>
            <button class="mini-btn" data-save="${scholarship.id}">${state.discoverSaved.includes(scholarship.id) ? "Bookmarked" : "Save"}</button>
            <button class="mini-btn danger" data-remove="${scholarship.id}">Not interested</button>
          </div>
        </div>
      `));
    });
  }

  recommendationsWrap.appendChild(recommendationCards);

  recommendationsWrap.querySelectorAll("[data-save]").forEach((button) => {
    button.onclick = () => {
      const id = button.getAttribute("data-save");
      if (state.discoverSaved.includes(id)) {
        state.discoverSaved = state.discoverSaved.filter((currentId) => currentId !== id);
      } else {
        state.discoverSaved = [...new Set([...state.discoverSaved, id])];
      }
      render();
    };
  });

  recommendationsWrap.querySelectorAll("[data-remove]").forEach((button) => {
    button.onclick = () => {
      const id = button.getAttribute("data-remove");
      state.discoverRemoved = [...new Set([...state.discoverRemoved, id])];
      state.discoverSelected = state.discoverSelected.filter((currentId) => currentId !== id);
      state.discoverCompare = state.discoverCompare.filter((currentId) => currentId !== id);
      state.discoverSaved = state.discoverSaved.filter((currentId) => currentId !== id);
      render();
    };
  });

  wrap.appendChild(recommendationsWrap);

  wrap.querySelector("#discover-reset").onclick = () => {
    state.discoverFilters = { country: "All", course: "All", degree: "All", funding: "All", deadline: "All" };
    state.discoverSelected = [];
    state.discoverCompare = [];
    state.discoverRemoved = [];
    state.discoverSaved = [];
    render();
  };

  return wrap;
}

/* ---------------- Init ---------------- */
render();
