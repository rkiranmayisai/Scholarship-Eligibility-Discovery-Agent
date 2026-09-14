# ScholarAI — Personal Scholarship Discovery Agent

**PS-016 — Scholarship Eligibility Discovery Agent**


> "Don't search for scholarships. Let AI find the ones you're eligible for."

ScholarAI is a multi-agent AI system that takes a student's profile, discovers
relevant scholarships, checks eligibility requirement-by-requirement, explains
*why* the student does or doesn't qualify, and produces a personalized
document checklist, deadline tracker, and day-by-day application plan.

This is **not** a chatbot or a filtered database view. Seven specialized
agents, coordinated by a central orchestrator, each own one part of the
reasoning pipeline and hand structured output to the next.

---

## 1. Why this is Agentic AI (not a chatbot)

| Trait | How ScholarAI demonstrates it |
|---|---|
| Multiple specialized roles | 7 agents, each with a single responsibility (see below) — not one LLM prompt doing everything |
| Autonomous decisions | The Profile Agent decides for itself whether it has enough information, and generates its own follow-up questions |
| Tool use | Each agent calls dedicated tools (rule evaluator, vector search, deadline calculator, document mapper) rather than "asking an LLM" for the answer |
| Explainable reasoning | Every eligibility verdict shows requirement-by-requirement PASS/FAIL/UNKNOWN with a plain-language explanation — never a bare yes/no |
| Retrieval before generation | The Discovery Agent runs a TF-IDF vector-similarity retrieval pass (a genuine RAG step) over the scholarship knowledge base before any ranking happens |
| Orchestrated hand-off | The Orchestrator passes structured Pydantic objects between agents — Discovery's output *is* Eligibility's input *is* Ranking's input, and so on |
| Visible agent activity | The right-hand "Agent Activity" panel shows, live, what each agent did and why — this is deliberately surfaced so the multi-agent behavior is visible, not hidden inside a single black-box response |

---

## 2. Agent responsibilities

1. **Profile Analyzer Agent** — parses free text or a structured form into a
   `StudentProfile`, decides if critical fields (state, course, year, CGPA,
   income, category) are missing, and generates targeted follow-up questions.
2. **Discovery Agent** — coarse-filters the scholarship knowledge base, then
   runs semantic (TF-IDF vector) retrieval against the student's profile.
3. **Eligibility Analyzer Agent** — evaluates every individual requirement
   (course, CGPA/percentage, income, state, category, gender, year, age,
   disability) and classifies each scholarship 🟢 ELIGIBLE / 🟡 ALMOST
   ELIGIBLE / 🔴 NOT ELIGIBLE, with a full explanation per requirement.
4. **Ranking Agent** — computes an explainable match score (0–99%) from
   eligibility confidence, profile relevance, deadline urgency, scholarship
   amount, and direct-match bonuses (state/category/gender).
5. **Document Checklist Agent** — builds a per-scholarship and a combined
   master document checklist, and lets the student mark documents as
   available.
6. **Deadline & Priority Agent** — classifies each actionable scholarship's
   deadline as 🔴 Urgent / 🟠 Apply Soon / 🟢 Later and recommends what to do
   first.
7. **Application Planner Agent** — synthesizes documents + deadlines +
   eligibility into a day-by-day action plan.

A central **Orchestrator** (`app/agents/orchestrator.py`) runs these in
sequence, passing structured data forward and recording an activity log for
the Agent Activity panel.

```
Student
  ↓
Profile Analyzer Agent
  ↓
Agent Orchestrator
  ↓
Discovery Agent  →  (RAG: TF-IDF vector retrieval over local knowledge base)
  ↓
Eligibility Agent  →  (rule-by-rule PASS/FAIL/UNKNOWN)
  ↓
Ranking Agent  →  (explainable match score)
  ↓
Document Agent  →  (per-scholarship + master checklist)
  ↓
Deadline Agent  →  (urgency classification)
  ↓
Application Planner Agent  →  (day-by-day plan)
  ↓
Final Personalized Scholarship Dashboard
```

---

## 3. Tech stack

- **Backend:** Python + FastAPI
- **Agents:** plain Python classes coordinated by a central Orchestrator
  (kept dependency-light on purpose — swap in LangGraph by wrapping each
  agent's `.run()` as a graph node if you want an explicit graph runtime)
- **Database:** SQLite by default (zero config); swap `DATABASE_URL` in
  `.env` for Postgres/Supabase — the SQLAlchemy schema doesn't change
- **RAG / retrieval:** scikit-learn TF-IDF + cosine similarity over the
  scholarship knowledge base (works fully offline, no embeddings API
  required; swap for FAISS/Chroma/pgvector by replacing
  `app/tools/vector_search_tool.py`)
- **LLM (optional):** OpenAI or Gemini, used only to improve free-text
  profile parsing and chat phrasing — **the app is fully functional with
  `LLM_PROVIDER=none`**, since all eligibility/ranking/planning logic is
  deterministic and rule-based (this is also what makes the eligibility
  decisions auditable rather than hallucinated)
- **Frontend:** plain HTML/CSS/JS single-page app (no build step) — swap in
  React + Tailwind by porting `frontend/app.js`'s render functions into
  components if desired
- **Demo dataset:** 22 scholarship records covering national (NSP, AICTE,
  UGC), Telangana state (ePASS and department-specific), and private/CSR
  sources — all explicitly marked `DEMO DATA` with a `last_verified` date

---

## 4. Folder structure

```
scholarai/
├── backend/
│   ├── app/
│   │   ├── main.py                  FastAPI app + all endpoints
│   │   ├── models.py                Pydantic schemas shared by agents
│   │   ├── database.py              SQLAlchemy models (SQLite default)
│   │   ├── llm_client.py            Optional OpenAI/Gemini wrapper
│   │   ├── agents/
│   │   │   ├── profile_agent.py
│   │   │   ├── discovery_agent.py
│   │   │   ├── eligibility_agent.py
│   │   │   ├── ranking_agent.py
│   │   │   ├── document_agent.py
│   │   │   ├── deadline_agent.py
│   │   │   ├── planner_agent.py
│   │   │   ├── chat_agent.py         Grounded Q&A over agent results
│   │   │   └── orchestrator.py       Coordinates all agents
│   │   ├── tools/
│   │   │   ├── profile_extraction_tool.py
│   │   │   ├── scholarship_db_tool.py
│   │   │   ├── vector_search_tool.py  RAG retrieval (TF-IDF)
│   │   │   ├── eligibility_rule_tool.py
│   │   │   ├── document_tool.py
│   │   │   └── deadline_tool.py
│   │   └── data/
│   │       └── scholarships.json     22 demo scholarship records
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html
    ├── styles.css
    └── app.js
```

---

## 5. Installation & running locally

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # defaults work as-is, no keys required
uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000`. Interactive docs (Swagger)
are auto-generated at `http://localhost:8000/docs`.

### Frontend

The frontend is a static site with no build step.

```bash
cd frontend
python3 -m http.server 5500
```

Open `http://localhost:5500` in your browser. If your backend runs on a
different host/port, set it before the page loads:

```html
<script>window.SCHOLARAI_API_BASE = "http://localhost:8000";</script>
```
(add this line in `index.html` above the `app.js` script tag)

### Enabling the live Discovery pipeline (optional)

By default the Discovery Agent only searches the 22-record local demo
dataset. With Google credentials configured, it runs a full real-world
discovery pipeline instead of a simple keyword lookup:

**Setup (2 steps, same as before):**
1. Create a Programmable Search Engine at
   https://programmablesearchengine.google.com/ → turn on **"Search the
   entire web"** → copy the **Search engine ID** (`cx`).
2. Enable the Custom Search API and get an API key at
   https://console.cloud.google.com/apis/library/customsearch.googleapis.com

   ```
   # backend/.env
   GOOGLE_API_KEY=your_api_key_here
   GOOGLE_CSE_ID=your_search_engine_id_here
   ```

**What the pipeline actually does** (`app/agents/discovery_agent.py`):

1. **Multi-query search** — builds profile-aware queries (course, branch,
   year, state, category) plus generic queries ("engineering scholarship
   India", "NSP engineering scholarship", etc.), respecting a query
   budget to stay within Google's free 100/day quota.
2. **Source tiering** (`tools/source_tiers.py`) — classifies every result
   domain as TIER1 (government: `.gov.in`, AICTE, UGC, NSP, state
   welfare departments), TIER2 (universities, corporate/NGO foundations),
   or TIER3 (aggregators like Buddy4Study) — tier drives how much a
   record can be trusted.
3. **Page fetch + extraction with evidence** (`tools/page_fetch_tool.py`,
   `tools/scholarship_extraction_tool.py`) — fetches the actual source
   page and extracts CGPA, income limit, category, documents, deadline,
   etc., **each with the literal sentence it was read from and the
   source URL** stored as evidence. Nothing is guessed: a field with no
   match in the page stays `null`/`"Not specified"`.
4. **Verification status** — `VERIFIED` only for TIER1 sources with
   enough confirmed eligibility fields; everything else is
   `NEEDS_VERIFICATION`; a passed deadline is `EXPIRED` regardless of
   tier. TIER3 aggregator-only finds can never be marked `VERIFIED`
   (the spec requires locating the original provider first).
5. **Data-quality rejection** (`tools/data_quality_tool.py`) — drops
   records missing a name/provider/source, or that read as pure ads
   with no extractable eligibility signal at all.
6. **Deduplication** (`tools/dedup_tool.py`) — groups by normalized
   `provider + scholarship_name`, keeps the highest-tier/most-verified
   record as primary, files the rest as `secondary_sources`.
7. **Schema conversion + persistence** (`tools/schema_converter_tool.py`,
   `database.upsert_live_scholarships`) — converts into the app's
   internal schema (so Eligibility/Ranking/Document/Deadline agents
   don't need to know two schemas) and upserts into the `scholarships`
   table, tracking newly-added vs. updated vs. unchanged records.
8. **RAG retrieval** — merges into the same TF-IDF vector search as the
   demo dataset, so live and demo scholarships are ranked together.

**Every live result carries its evidence into the UI** — click a
scholarship card and the "Why you qualify" modal shows the exact quote
each field was extracted from, with a link to the source page, plus any
secondary sources the same scholarship was also found on.

**Continuous update:** call `POST /api/discovery/refresh` to run a
full-catalog discovery pass (generic queries, not tied to one student)
and re-check stored scholarships for expiry. Wire this to a nightly
cron job / scheduled task for periodic updates:
```bash
# example crontab entry, runs nightly at 2am
0 2 * * * curl -X POST http://localhost:8000/api/discovery/refresh
```
`GET /api/discovery/report` returns the stats from the most recent run
(discovered / extracted / verified / needs verification / expired /
duplicates removed / sources used / newly added / updated) — the exact
report shape the Discovery Agent spec requires.

**Known limitation:** deduplication matches on normalized
`provider + name` (as the spec specifies) rather than fuzzy text
similarity, so the same scholarship phrased very differently across two
listings (e.g. "NMMS" vs. "National Means-cum-Merit Scholarship") may
not be merged automatically. A fuzzy-matching upgrade (e.g. token-set
similarity) is a natural next step -- see "Future enhancements."

### Enabling an LLM (optional)

Not required — everything works with `LLM_PROVIDER=none`. To enable nicer
free-text parsing / chat phrasing:

```
# .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```
or
```
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
```
Then uncomment the matching line in `requirements.txt` and `pip install` again.

---

## 6. Demo flow (exact hackathon script)

1. Open the app → **Find My Scholarships**.
2. On the Student Profile page, paste (already pre-filled as an example):
   > "I am a third-year B.Tech CSE student from Telangana. My CGPA is 8.7 and my family income is ₹3 lakh per year."
3. Click **Run Scholarship Discovery**. Watch the **Agent Activity** panel on
   the right populate live as each of the 7 agents reports what it did.
4. Land on **Results**: summary counts (Eligible / Almost Eligible / Not
   Eligible), then ranked scholarship cards with match scores.
5. Click any scholarship card → the **Why You Qualify** modal shows every
   requirement, the student's value, PASS/FAIL/UNKNOWN, and an explanation.
6. Go to **Documents** → see the master checklist and tick off documents you
   already have.
7. Go to **Deadlines** → see Urgent / Apply Soon / Later groupings.
8. Go to **Action Plan** → see the day-by-day plan generated from all of the
   above.
9. Go to **AI Chat** → ask "Which one should I apply for first?" or "What
   documents do I need?" — answers are grounded in the same agent output
   shown in the dashboard (not a separate, ungrounded chatbot).

---

## 7. Example agent execution (from an actual run of this codebase)

Input: *"I am a third-year B.Tech CSE student from Telangana. My CGPA is 8.7
and my family income is 3 lakh per year."*

```
🤖 Profile Analyzer Agent
✓ Student profile analyzed -- 1 follow-up question(s) needed
   (category not stated)

🔎 Discovery Agent
✓ Retrieved 21 relevant scholarships from knowledge base (RAG retrieval)

⚖️ Eligibility Agent
✓ Checked 21 scholarships -- 0 eligible, 7 almost eligible, 14 not eligible
   (eligible count rises to 3 once category is supplied, e.g. "General")

📊 Ranking Agent
✓ Ranked 21 opportunities by explainable match score
   #1 Telangana State Engineering CGPA Excellence Award — 61.1% — Almost Eligible

📄 Document Agent
✓ Generated document checklist (8 unique documents across 7 actionable scholarships)

⏰ Deadline Agent
✓ Prioritized applications -- recommend starting with
   'Wipro Cares Scholarship for Engineering Students' (4 days remaining)

🧠 Planning Agent
✓ Created a 5-day personalized action plan
```

This exact scenario is reproducible by pasting the sample text into the
Student Profile page.

---

## 8. Database schema

| Table | Purpose |
|---|---|
| `students` | one row per session, stores the extracted profile JSON |
| `scholarships` | seeded from `data/scholarships.json` on first run |
| `eligibility_rules` | log of per-student, per-scholarship evaluation results |
| `documents` | per-student document checklist status |
| `applications` | tracked application status per student/scholarship |
| `deadlines` | scholarship deadline + priority |
| `agent_logs` | full audit trail of every agent action per session |

---

## 9. API summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | health check |
| GET | `/api/scholarships` | list the full local knowledge base |
| GET | `/api/scholarships/{id}` | single scholarship record |
| POST | `/api/discover` | run the full 7-agent pipeline on a profile |
| GET | `/api/session/{session_id}` | fetch a previous run's full result |
| POST | `/api/documents/update` | mark a document Available/Missing |
| POST | `/api/chat` | ask the grounded chat assistant a question |

---

## 10. Safety & reliability notes

- Every scholarship record is explicitly tagged `DEMO DATA` with a
  `last_verified` date — no record is presented as a live/verified source.
- The app never fabricates an application link or deadline; all values come
  from the local knowledge base or (if wired up) a real search tool result
  marked `VERIFIED SOURCE`.
- Eligibility results always show a confidence level and explicitly call out
  which values were "Not provided" (`UNKNOWN`), rather than assuming a pass.
- The UI disclaimer on the Results page and every eligibility modal reminds
  students to confirm on the official portal before applying.

---

## 11. Hackathon presentation points

- **Differentiator:** existing portals say "find scholarships"; ScholarAI
  says *"understand → discover → reason about eligibility → explain →
  prioritize → prepare documents → plan the action."*
- **Explainability over classification:** eligibility is never a bare
  yes/no — every requirement is shown with the source value, the student's
  value, and a plain-language explanation. The 🟡 Almost Eligible tier is a
  deliberate design choice to show students exactly what stands between
  them and qualifying.
- **Agentic, not a wrapper:** 7 agents with distinct responsibilities, tool
  calls, and a visible orchestration log — the Agent Activity panel exists
  specifically to make this visible to judges.
- **Works with zero API keys:** because eligibility logic is deterministic
  and RAG retrieval runs on local TF-IDF vectors, the whole system runs and
  demos reliably without any internet dependency or paid API — while still
  supporting a pluggable LLM for nicer natural-language parsing/chat.

---

## 12. Future enhancements

- Wire up a real web-search tool (Tavily/SerpAPI) in
  `discovery_agent.web_search_stub` for live scholarship discovery, storing
  results as `VERIFIED SOURCE` with retrieval date, merged alongside (never
  silently replacing) the demo dataset.
- Swap TF-IDF retrieval for a hosted embeddings model + FAISS/Chroma/pgvector
  for larger, semantically richer knowledge bases.
- Add authentication so students can save profiles and track applications
  across sessions (schema already supports this via `students`/`applications`).
- Turn the Orchestrator into an explicit LangGraph graph for visual
  debugging of agent state transitions.
- OCR-based document verification (upload a certificate, auto-check it
  against the requirement).
- SMS/email deadline reminders via the `deadlines` table.
