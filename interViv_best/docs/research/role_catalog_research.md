# Role catalog research (draft input)

Status: draft input for role blueprints. Not reviewed content, and not a question bank.

Use the competencies, weights, level expectations and sample questions below as drafts. Verify occupation mappings before use. Do not cite the statistics below as finished claims.

Known limits:

- Spoken questions here often run 60 to 90 words. In voice mode a spoken question stays at about 40 words and two sentences. Extra parts become follow-ups.
- Scorer v3 was validated on short computer-science answers. Scenario answers for business, product and design roles count as practice, not readiness, until a human-graded check of about 30 answers per family shows the scorer agrees with people.
- Weak occupation mappings to verify: Associate Product Manager to O*NET IT Project Managers, DevOps toward network administrators, Data Engineer to the ESCO data scientist occupation, Cybersecurity to the ESCO ICT system administrator occupation.
- Deloitte reports that 86 percent of organisations say AI is transforming hiring. This file's wording that 86 percent embed AI across screening and evaluation is a rewording. The 75 percent behavioural-competency and 72 percent learning-agility figures are not confirmed. Do not cite those three until checked.
- The 20/10/60/10 STAR split is advice on time spent. Use it for coaching, not as a score.

---

## Research Foundation for Role-Based Interviews

Organizing mock interviews around standardized **role blueprints** (position plus seniority level) rather than company-specific trivia aligns directly with personnel selection science and modern campus recruitment practices. In a landmark meta-analytic re-evaluation of selection predictors, Sackett et al. (2022) ranked **structured interviews** first among all hiring methods with a mean operational validity of **0.42** (80% credibility interval of **0.18 to 0.66**), outperforming empirically keyed biodata (**0.38**), assessment centers (**0.33**), cognitive ability tests (**0.31**), and unstructured interviews (**0.19**) ([Cambridge Core](https://www.cambridge.org/core/journals/industrial-and-organizational-psychology/article/revisiting-the-design-of-selection-systems-in-light-of-new-findings-regarding-the-validity-of-widely-used-predictors/A20984B138319E3D432E643978BF026D); [Noon AI](https://www.noon.ai/blog/articles/356-structured-interview-validity)). Squaring those validity coefficients indicates that structured interviews account for roughly **18%** of the variance in rated job performance compared with roughly **4%** for unstructured conversations ([Noon AI](https://www.noon.ai/blog/articles/356-structured-interview-validity)).

Campus hiring in India has shifted decisively toward this same competency-driven model. Surveying **257 organizations** and **505 campuses**, Deloitte India's **Campus Workforce Trends 2026** study reports that campus recruitment budgets rose **19%**, **86%** of employers now embed AI across screening and candidate evaluation (**72%** in resume screening and **48%** in assessments), and employers prioritize structured, skill-based shortlisting over generic pedigree ([Deloitte India 2026](https://www.deloitte.com/in/en/about/press-room/india-s-campus-talent-landscape-pivots-to-skill-based-hiring-as-86-percent-of-employers-adopt-ai-in-recruitment--deloitte-india.html)). Crucially for interview design, employers report **20–25%** compensation premiums for AI, data science, and cybersecurity skills, **10–15%** premiums for analytical problem-solving, and rank **behavioural competencies (75%)** and **learning agility (72%)** as the strongest predictors of internship-to-pre-placement-offer (PPO) conversion ([Deloitte India 2026](https://www.deloitte.com/in/en/about/press-room/india-s-campus-talent-landscape-pivots-to-skill-based-hiring-as-86-percent-of-employers-adopt-ai-in-recruitment--deloitte-india.html)).

Existing interview-prep tools cover fragments of this workflow without combining verified occupational blueprints and rubric-locked scoring. Google Interview Warmup groups practice into six broad job fields (Data Analytics, E-Commerce, IT Support, Project Management, UX Design, and General) and asks background, situational, and technical questions without grading answers ([9to5Google](https://9to5google.com/?p=502626)). Final Round AI generates personalized question-and-answer pairs directly from uploaded resumes and pasted job descriptions ([Unite.AI](https://www.unite.ai/final-round-ai-review)), which risks unverified rubrics when a language model invents both the question and the grading standard. Grounding every role blueprint in two public occupational taxonomies—the **O\*NET 31.0 Database** covering **1,016 occupations** and **31,821 software skill linkages** under a CC BY 4.0 license ([O\*NET Resource Center](https://www.onetcenter.org/database.html)) and the **European Skills, Competences, Qualifications and Occupations (ESCO)** API—ensures that every role tests empirically verified tasks, tools, and work styles while reusing shared technical question bundles across roles.

---

## Master Role Catalog and Competency Matrix

Both the U.S. Office of Personnel Management (OPM) and Google re:Work recommend anchoring each structured interview to **4 to 8 job-related competencies** spanning role-related technical knowledge, situational problem-solving, and behavioural attributes ([U.S. OPM](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/structured-interviews); [Google re:Work](https://rework.withgoogle.com/intl/en/guides/a-guide-to-structured-interviewing-for-better-hiring-practices?hl=en-US)). The starter catalog below covers **12 high-volume campus and early-career roles** across five families (Engineering, Data, Business, Product, and Design), supplemented by **2 priority expansion roles** (Data Engineer and Cybersecurity Analyst) where employer skill premiums are highest ([Deloitte India 2026](https://www.deloitte.com/in/en/about/press-room/india-s-campus-talent-landscape-pivots-to-skill-based-hiring-as-86-percent-of-employers-adopt-ai-in-recruitment--deloitte-india.html)).

| Role Title & ID | Family | Common Campus & Job Aliases | Grounded O\*NET-SOC Code | Grounded ESCO Occupation (ISCO) | Competency Split (Tech / Scenario / Behav.) | Practical Track |
|---|---|---|---|---|---|---|
| **Backend Engineer** (`backend-engineer`) | Engineering | SDE-1 (Backend), API Developer, Server-Side Engineer, Java/Python Developer | [15-1252.00 Software Developers](https://www.onetonline.org/link/summary/15-1252.00) | [software developer (2512.3)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Ff2b15a0e-e65a-438a-affb-29b9d50b77d1&language=en) | 0.60 / 0.20 / 0.20 | Coding |
| **Frontend Engineer** (`frontend-engineer`) | Engineering | UI Engineer, SDE-1 (Frontend), React/Web Developer | [15-1254.00 Web Developers](https://www.onetonline.org/link/summary/15-1254.00) | [user interface developer (2512.4)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F866c7813-2c03-47d7-9bdc-192cfbace57c&language=en) | 0.60 / 0.20 / 0.20 | Coding |
| **Full-Stack Engineer** (`fullstack-engineer`) | Engineering | SDE-1, Full-Stack Web Developer, Software Engineer Trainee, GET (Software) | [15-1252.00](https://www.onetonline.org/link/summary/15-1252.00) & [15-1254.00](https://www.onetonline.org/link/summary/15-1254.00) | [web developer (2513.5)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Fc40a2919-48a9-40ea-b506-1f34f693496d&language=en) | 0.60 / 0.20 / 0.20 | Coding |
| **DevOps / Cloud Engineer** (`devops-cloud-engineer`) | Engineering | SRE Intern/Junior, Cloud Infrastructure Engineer, Platform Engineer, Build & Release Engineer | [15-1244.00](https://www.onetonline.org/link/summary/15-1244.00) & [15-1241.00](https://www.onetonline.org/link/summary/15-1241.00) | [ICT system administrator (2522.1)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F9e2e6e1e-363b-4e1b-a673-7bc0f7343300&language=en) | 0.60 / 0.20 / 0.20 | None |
| **QA / Test Engineer** (`qa-test-engineer`) | Engineering | SDET, Automation Test Engineer, Quality Assurance Analyst | [15-1253.00 Software QA Analysts & Testers](https://www.onetonline.org/link/summary/15-1253.00) | [software tester (2519.6)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F106f79e4-6264-45f1-9e7a-297435cd684b&language=en) | 0.55 / 0.25 / 0.20 | Coding |
| **Data Analyst** (`data-analyst`) | Data | BI Analyst, Business Data Analyst, Product/Decision Analyst, Analytics Associate | [15-2051.01 Business Intelligence Analysts](https://www.onetonline.org/link/summary/15-2051.01) | [data analyst (2511.2)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Fd3edb8f8-3a06-47a0-8fb9-9b212c006aa2&language=en) | 0.55 / 0.30 / 0.15 | SQL |
| **Data Scientist / ML Engineer** (`data-scientist-ml`) | Data | Junior Data Scientist, Applied AI/ML Engineer, ML Associate, Decision Scientist | [15-2051.00 Data Scientists](https://www.onetonline.org/link/summary/15-2051.00) | [data scientist (2511.3)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F258e46f9-0075-4a2e-adae-1ff0477e0f30&language=en) | 0.60 / 0.20 / 0.20 | Coding |
| **Business Analyst** (`business-analyst`) | Business | IT Business Analyst, Systems Analyst, Strategy/Management Analyst Trainee | [15-1211.00](https://www.onetonline.org/link/summary/15-1211.00) & [13-1111.00](https://www.onetonline.org/link/summary/13-1111.00) | [ICT business analyst (2511.8)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Ffe0fa514-b48d-4a53-9757-a283c0baacf0&language=en) | 0.45 / 0.30 / 0.25 | SQL |
| **Associate Product Manager** (`associate-product-manager`) | Product | APM, Product Analyst, Junior Product Manager, Digital PM Trainee | [15-1299.09 IT Project Managers](https://www.onetonline.org/link/summary/15-1299.09) | [ICT product manager (1330.6)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Fa79170ad-0b7b-4697-864f-1748359aa10a&language=en) | 0.45 / 0.30 / 0.25 | None |
| **Product Marketing** (`product-marketing`) | Business | PMM Associate, Growth Marketing Analyst, GTM Specialist, Market Research Associate | [13-1161.00 Market Research & Marketing](https://www.onetonline.org/link/summary/13-1161.00) | [marketing manager (1221.3.2)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F6fcf4638-e7c7-4978-9302-9a7b63a3d57c&language=en) | 0.45 / 0.30 / 0.25 | None |
| **UI/UX Designer** (`ui-ux-designer`) | Design | Product Designer, Interaction Designer, UX Researcher & Designer, Digital Designer | [15-1255.00 Web & Digital Interface Designers](https://www.onetonline.org/link/summary/15-1255.00) | [UI designer (2513.3)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F96e20037-0a25-4bf6-a25e-808d1605d890&language=en) & [UX analyst (2511.18)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Ffaed411a-f920-4100-86a8-b877928b429c&language=en) | 0.50 / 0.25 / 0.25 | None |
| **Operations / Project Coordinator** (`operations-project-coordinator`) | Business | Project Coordinator, Program Associate, PMO Analyst, Business Operations Associate | [13-1082.00 Project Management Specialists](https://www.onetonline.org/link/summary/13-1082.00) | [project manager (1219.6)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Fbea99fea-0383-4c63-b944-70d4799de2c5&language=en) | 0.45 / 0.30 / 0.25 | None |
| **Expansion: Data Engineer** (`data-engineer`) | Data | ETL Developer, Analytics Engineer, Big Data Engineer | [15-1243.00 Database Architects](https://www.onetonline.org/link/summary/15-1243.00) | [data scientist / data engineer (2511.3)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F258e46f9-0075-4a2e-adae-1ff0477e0f30&language=en) | 0.60 / 0.20 / 0.20 | SQL |
| **Expansion: Cybersecurity Analyst** (`cybersecurity-analyst`) | Engineering | SOC Analyst, InfoSec Analyst, Application Security Trainee | [15-1212.00 Information Security Analysts](https://www.onetonline.org/link/summary/15-1212.00) | [ICT system administrator (2522.1)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F9e2e6e1e-363b-4e1b-a673-7bc0f7343300&language=en) | 0.60 / 0.20 / 0.20 | None |

The chart below illustrates how competency weights shift systematically across families: core engineering and data-science roles allocate **55% to 60%** of blueprint weight to technical fundamentals and pair them with a **Coding** or **SQL** practical track, while business, product, and design roles allocate **25% to 30%** to role scenarios and **25%** to behavioural competencies so Quick-mode sessions still capture realistic trade-off reasoning.

The competency-weight chart is omitted. The source was a temporary signed link that expires.

---

## Question Archetypes, Calibration Rules, and Evaluation Standards

Every role-based interview draws from **six distinct question slots**, separating objective rubric scoring (used only where a vetted, shared reference answer exists) from personalized coaching insights (used where content is candidate-specific or narrative) ([U.S. OPM](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/structured-interviews); [Google re:Work](https://rework.withgoogle.com/intl/en/guides/a-guide-to-structured-interviewing-for-better-hiring-practices?hl=en-US)).

| Question Slot | What It Tests | How Level & Resume Calibrate It | Evaluation & Readiness Rule |
|---|---|---|---|
| **1. Resume / Project Opener** | Authenticity of project ownership, architectural choice, trade-offs, and debugging experience ([Google re:Work](https://rework.withgoogle.com/intl/en/guides/a-guide-to-structured-interviewing-for-better-hiring-practices?hl=en-US)) | With a resume: probes a named project + tool (e.g., why Redis vs. Postgres). Without a resume: easy role-entry warm-up | **Unscored coaching only** (checks choice justification, trade-off awareness, concrete outcome; excluded from readiness) |
| **2. Core Skill — Fundamentals** | Baseline conceptual clarity, mechanism accuracy, and standard usage | Assigned to **Intern/Junior** slots and any required skill marked **missing** or **listed_only** on the resume | **Scored** against hidden reference answer (counts toward role readiness only when bundle status is `reviewed`) |
| **3. Core Skill — Deep & Trade-Offs** | Internal mechanics, edge cases, scaling bottlenecks, and failure modes | Assigned to **Mid** level or one level harder on any skill marked **claimed_with_evidence** on the resume | **Scored** against hidden reference answer (counts toward role readiness when `reviewed`) |
| **4. Role Scenario (Situational)** | Applied judgment in realistic critical incidents specific to the target role ([U.S. OPM](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/structured-interviews)) | **Intern/Junior**: structured diagnosis and safe escalation. **Mid**: root-cause isolation, stakeholder trade-offs, and prevention | **Scored** against hidden required scenario concepts (e.g., metric reconciliation, rollback vs. hotfix) |
| **5. Behavioural (STAR)** | Past actions demonstrating ownership, collaboration, conflict resolution, or learning agility ([MIT CAPD](https://capd.mit.edu/resources/the-star-method-for-behavioral-interviews/)) | Prompts use superlative anchors ("most challenging", "hardest trade-off") recommended by [U.S. OPM](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/structured-interviews) | **Unscored STAR coaching** checking Situation (20%), Task (10%), personal Action (60%), and quantified Result (10%) ([MIT CAPD](https://capd.mit.edu/resources/the-star-method-for-behavioral-interviews/)) |
| **6. Practical & Follow-Up Probes** | Hands-on execution (Coding/SQL) plus non-leading follow-ups on missed concepts | Follow-ups trigger only on missed required concepts (max 1 per question, 2 per block); probes clarify vague "we" statements ([U.S. OPM](https://www.opm.gov/policy-data-oversight/assessment-and-selection/structured-interviews/structured-interviews)) | **Practical** is scored by test cases/queries; **Follow-ups** are unscored diagnostic coaching |

---

## Complete Role Blueprints, Required Skills, and Sample Questions

### 1. Backend Engineer (`backend-engineer`)

- **Grounding & Provenance**: Grounded in O\*NET [15-1252.00 Software Developers](https://www.onetonline.org/link/summary/15-1252.00) (analyzing requirements for design feasibility, modifying software to correct errors and improve performance, and using Hot Technologies including Spring Boot, PostgreSQL, Redis, Amazon DynamoDB, Apache Kafka, GraphQL, Git, and JUnit) and ESCO [software developer (ISCO 2512.3)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Ff2b15a0e-e65a-438a-affb-29b9d50b77d1&language=en) (engineering principles, debugging software, automated migration methods, and technical documentation).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **Coding** (data structures, API data transformation, concurrency/rate-limiting logic).
- **Level Expectations**:
  - **Intern / Junior**: Writes clean Python or Java endpoints, explains HTTP status codes and idempotency, normalizes relational tables with proper primary/foreign keys and indexes, and understands process vs. thread fundamentals.
  - **Mid**: Designs pagination, caching invalidation, database transaction isolation levels, connection pooling, asynchronous queues, and observability under load.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **Backend Programming (Python / Java)** | Technical | 0.20 | `Python`, `Java`, `OOP` (concurrency, memory model, exception handling, typing) |
| **Database Management Systems (DBMS)** | Technical | 0.15 | `DBMS`, `SQL` (indexing, ACID transactions, normalization, query plans, caching) |
| **REST APIs & Service Design** | Technical | 0.15 | `REST APIs` (HTTP semantics, idempotency, authentication/JWT, rate limiting, versioning) |
| **Operating Systems & Runtime Basics** | Technical | 0.10 | `Operating Systems` (processes vs. threads, deadlocks, I/O blocking, memory management) |
| **Production Debugging & Reliability** | Role Scenario | 0.20 | Latency spikes, N+1 query regressions, race conditions in payment/order flows, safe rollbacks |
| **Ownership & Engineering Rigor** | Behavioural | 0.10 | Taking end-to-end responsibility for bugs, testing edge cases, post-incident follow-through |
| **Cross-Team Technical Collaboration** | Behavioural | 0.10 | Resolving API contract mismatches with frontend, QA, or mobile teammates |

**Representative Questions Asked in Backend Engineer Interviews:**
- **Resume / Project Opener (Unscored Coaching)**: "In your e-commerce backend project, you used JWT authentication and Redis caching. Why did you cache product listings in Redis instead of relying on PostgreSQL indexes, and how did you prevent stale prices when an admin updated inventory?"
  - **Coaching Check**: Verifies concrete justification (read-heavy traffic vs. DB load), cache invalidation strategy (TTL vs. write-through/eviction), and awareness of failure modes if Redis goes down.
- **Core Technical — Fundamentals (Intern / Junior or Missing Skill)**: "What makes an HTTP method idempotent, why is PUT considered idempotent while POST typically is not, and how would you prevent duplicate charges if a client retries a POST /payments request after a network timeout?"
  - **Hidden Reference Concepts**: Definition of idempotency (identical server state across repeated identical requests); `GET`/`PUT`/`DELETE` vs. `POST`; client-generated `Idempotency-Key` stored atomically with unique constraint or lock.
- **Core Technical — Deep / Trade-Off (Mid or Claimed Skill)**: "Two concurrent transactions read a user's wallet balance of 500, verify sufficient funds, and each deduct 400. Which SQL isolation phenomena is occurring, why does Read Committed fail to stop it without explicit locking, and how do SELECT FOR UPDATE vs. optimistic concurrency version columns trade off under high contention?"
  - **Hidden Reference Concepts**: Lost update anomaly; `READ COMMITTED` allows concurrent reads before commit; pessimistic row lock (`SELECT ... FOR UPDATE`) serializes hot rows vs. optimistic `version` check (`WHERE id = ? AND version = ?`) which avoids lock wait but increases retries under contention.
- **Role Scenario (Situational Scored)**: "Ten minutes after deploying a minor release to the order-history service, p95 API latency jumps from 120 ms to 4.2 seconds and database CPU hits 98%, though error rates are still below 1%. Walk through your first 15 minutes of triage and how you decide between rolling back and debugging live."
  - **Hidden Required Concepts**: Mitigate user impact first (correlate deploy timestamp and roll back or shift canary traffic if regression is tied to release); inspect slow-query logs / connection pool saturation / missing index or N+1 query; preserve diagnostic evidence (metrics, query plan) before/after rollback; communicate status clearly.
- **Behavioural (STAR)**: "Tell me about the hardest bug or system failure you had to track down in a project or internship where your first hypothesis turned out to be wrong. How did you narrow down the real cause, and what changed afterward?"
  - **Non-Leading Follow-Up Probe**: "What specific instrumentation or test did you personally add so that class of bug would be caught before deployment?"
- **Practical Round (Coding)**: Implement a thread-safe or timestamp-driven **sliding-window rate limiter** (or log aggregator deduplicating events per `user_id` within `W` seconds) with clean edge-case tests.

---

### 2. Frontend Engineer (`frontend-engineer`)

- **Grounding & Provenance**: Grounded in O\*NET [15-1254.00 Web Developers](https://www.onetonline.org/link/summary/15-1254.00) (writing code for web applications, ensuring cross-browser/device compatibility, analyzing user needs, and using Hot Technologies including TypeScript, React, Bootstrap, Figma, Jest/Selenium, and Git) and ESCO [user interface developer (ISCO 2512.4)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F866c7813-2c03-47d7-9bdc-192cfbace57c&language=en) (software UI design patterns, W3C standards, web programming, and user-centered design).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **Coding** (DOM/state logic, async debounce/cancellation, client data transformation).
- **Level Expectations**:
  - **Intern / Junior**: Understands closures, the event loop, promises, semantic HTML, CSS flexbox/grid, controlled vs. uncontrolled React components, and basic API state handling (loading, error, empty).
  - **Mid**: Diagnoses unnecessary re-renders, bundle bloat, Core Web Vitals (LCP, INP, CLS), race conditions in async data fetching, keyboard/ARIA accessibility, and client caching.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **JavaScript & TypeScript Core** | Technical | 0.25 | `JavaScript` (closures, event loop/microtasks, promises/AbortController, immutability, TypeScript types) |
| **React & Component Architecture** | Technical | 0.20 | `React` (state colocation, rendering lifecycle, hooks rules, custom hooks, forms, accessibility) |
| **Web Performance & Browser Mechanics** | Technical | 0.15 | `Web Performance`, `HTML/CSS` (CRP, Core Web Vitals, code splitting, caching, CORS/XSS basics) |
| **Diagnosing Degraded Client UX** | Role Scenario | 0.20 | Slow/janky pages reported by users, stale async search results, broken mobile/keyboard flows |
| **Attention to Craft & Accessibility** | Behavioural | 0.10 | Catching UX edge cases, empty/error states, and usability gaps proactively |
| **Designer–Backend Collaboration** | Behavioural | 0.10 | Negotiating feasible UI scope with designers and API shapes with backend engineers |

**Representative Questions Asked in Frontend Engineer Interviews:**
- **Resume / Project Opener**: "In your dashboard project built with React, you managed filter and table state across multiple charts. Where did that state live, why did you choose that approach over URL query parameters or a global store, and what happened if the user refreshed the page?"
- **Core Technical — Fundamentals**: "Explain how the JavaScript event loop schedules synchronous code, microtasks (Promise callbacks), and macrotasks (setTimeout). If a click handler queues both a Promise.then and a setTimeout(..., 0), in what order do they run relative to browser repaint?"
  - **Hidden Reference Concepts**: Call stack empties first; microtask queue drains completely before next render/macrotask; macrotask runs after microtasks (and potentially after repaint).
- **Core Technical — Deep / Trade-Off**: "A React search input fires a fetch request on every keystroke. When a user types 'react' quickly, the response for 're' arrives after the response for 'react' and overwrites the UI with stale results. Compare debouncing alone versus AbortController / request-ID guards, and explain why debouncing by itself does not eliminate the race condition."
  - **Hidden Reference Concepts**: Out-of-order network responses; debouncing reduces request count but slow earlier requests can still resolve after later ones; `AbortController` cancels in-flight fetch or cleanup `ignore` boolean / latest-request token discards stale responses.
- **Role Scenario**: "Users in Tier-2 cities on mid-range Android phones report that your product listing page takes 8 seconds to become interactive and freezes when scrolling through 500 items, even though it feels fast on your laptop. How do you reproduce, measure, and fix this systematically?"
  - **Hidden Required Concepts**: Throttle CPU and network in Chrome DevTools / Lighthouse; measure LCP, INP/TBT, bundle size, and React Profiler flamegraphs; virtualize/window the 500-row list; code-split heavy routes and optimize images.
- **Behavioural (STAR)**: "Describe a time when a design mockup or product requirement looked straightforward at first, but turned out to have tricky edge cases once you started building the UI. How did you handle it with the designer or PM?"
- **Practical Round (Coding)**: Implement an async `debounce` utility with cancellation (`cancel()` and `flush()`) or build a tree/nested-comment flattener and search filter handling empty/malformed nodes.

---

### 3. Full-Stack Engineer (`fullstack-engineer`)

- **Grounding & Provenance**: Grounded in O\*NET [15-1252.00 Software Developers](https://www.onetonline.org/link/summary/15-1252.00) and [15-1254.00 Web Developers](https://www.onetonline.org/link/summary/15-1254.00) alongside ESCO [web developer (ISCO 2513.5)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Fc40a2919-48a9-40ea-b506-1f34f693496d&language=en) (web programming, software design patterns, configuration management, debugging tools, and W3C standards).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **Coding**.
- **Level Expectations**:
  - **Intern / Junior**: Connects a React/JS frontend to a REST backend and relational DB, validates inputs on both client and server, handles authentication cookies/tokens safely, and writes basic SQL joins.
  - **Mid**: Designs end-to-end data contracts, prevents XSS/CSRF/IDOR vulnerabilities, manages optimistic UI updates with server rollback, and debugs cross-boundary latency from browser network tab to DB query plan.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **JavaScript & Frontend State** | Technical | 0.20 | `JavaScript`, `React` (async data fetching, forms, client state, XSS/CORS awareness) |
| **REST APIs & Auth Contracts** | Technical | 0.20 | `REST APIs` (payload schema design, pagination, session cookies vs. JWT, validation, error contracts) |
| **Database & Query Design** | Technical | 0.20 | `DBMS`, `SQL` (schema relations, indexes, transactions, avoiding N+1 across ORM boundaries) |
| **End-to-End Feature Delivery & Triage** | Role Scenario | 0.20 | Shipping a feature across UI, API, and DB safely; diagnosing bugs that cross frontend/backend boundaries |
| **End-to-End Ownership** | Behavioural | 0.10 | Delivering complete slices without dropping edge cases between frontend and backend |
| **Adaptability & Learning Agility** | Behavioural | 0.10 | Context-switching across stack layers and picking up unfamiliar libraries quickly |

**Representative Questions Asked in Full-Stack Engineer Interviews:**
- **Resume / Project Opener**: "Walk me through a single user action in your full-stack project—from clicking Submit in the browser to committing the row in the database and updating the screen. Where could that flow fail halfway, and how does your app handle it?"
- **Core Technical — Fundamentals**: "Why is client-side form validation never sufficient on its own, and what is the difference between stored XSS, CSRF, and an Insecure Direct Object Reference (IDOR) in a web app?"
  - **Hidden Reference Concepts**: Clients can bypass browser UI via curl/DevTools; XSS injects untrusted script into rendered DOM; CSRF tricks an authenticated browser into cross-site state-changing requests (`SameSite` cookies / CSRF tokens); IDOR accesses another user's record by changing an ID without server-side ownership authorization.
- **Core Technical — Deep / Trade-Off**: "Compare cursor-based pagination against LIMIT/OFFSET pagination for an infinite-scroll activity feed backed by PostgreSQL. What happens to both UI consistency and database query cost when new items are inserted at the top while the user scrolls to page 50?"
  - **Hidden Reference Concepts**: `OFFSET` scans and discards skipped rows (degrading linearly with depth) and causes duplicate/skipped items in UI when new rows shift offsets; cursor pagination (`WHERE (created_at, id) < (?, ?)`) uses composite B-tree index in constant index-seek time and preserves stable feed ordering, at the cost of no arbitrary page-number jumps.
- **Role Scenario**: "You need to ship a collaborative 'Invite Teammate by Email' feature end-to-end by Friday: UI modal, API endpoint, invitation token table, and email dispatch. How do you design the schema, API contract, failure handling if the email provider times out, and rollout steps?"
  - **Hidden Required Concepts**: Unique hashed token with expiry + role/tenant scoping; idempotent invite creation; decouple slow SMTP/email API via background job/outbox or graceful retry status so DB transaction isn't held open during external HTTP call; authorization check that only admins can invite.
- **Behavioural (STAR)**: "Tell me about a time you had to jump into an unfamiliar part of the stack—frontend, backend, or deployment—under a tight deadline. How did you get unblocked without breaking existing behaviour?"
- **Practical Round (Coding)**: Transform flat relational API records into a paginated, sorted summary payload (or implement request batching / validation middleware).

---

### 4. DevOps / Cloud Engineer (`devops-cloud-engineer`)

- **Grounding & Provenance**: Grounded in O\*NET [15-1244.00 Network and Computer Systems Administrators](https://www.onetonline.org/link/summary/15-1244.00) and [15-1241.00 Computer Network Architects](https://www.onetonline.org/link/summary/15-1241.00) (disaster recovery, network security, system troubleshooting, and Hot/In-Demand technologies including Docker, Red Hat OpenShift, AWS CloudFormation, EC2, S3, Chef/Puppet/Terraform/Ansible, Bash/UNIX Shell, Git, Splunk, and In-Demand Firewall software) and ESCO [ICT system administrator (ISCO 2522.1)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F9e2e6e1e-363b-4e1b-a673-7bc0f7343300&language=en) (maintaining ICT systems, managing system security, solving system problems, and integrating components).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **None** (focused on container, cloud IAM/networking, CI/CD, and incident scenario depth).
- **Level Expectations**:
  - **Intern / Junior**: Writes clean multi-stage Dockerfiles, explains Linux permissions/processes/ports, configures basic GitHub Actions/GitLab CI pipelines, and understands VPC subnets, security groups, and IAM least privilege.
  - **Mid**: Designs zero-downtime deployments (blue/green, canary), Infrastructure-as-Code state locking and drift remediation, secrets management, observability (metrics/logs/traces, SLOs), and structured incident response.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **Containers & Docker** | Technical | 0.20 | `Docker` (image layers, multi-stage builds, non-root security, volumes, container networking) |
| **Cloud Infrastructure (AWS)** | Technical | 0.15 | `AWS` (IAM least privilege, VPC public/private subnets, NAT/IGW, EC2/ALB, S3 security) |
| **CI/CD & Deployment Automation** | Technical | 0.15 | `CI/CD` (build/test/deploy stages, artifact immutability, secrets handling, rollback strategies) |
| **Networking & Linux Systems** | Technical | 0.10 | `Computer Networks`, `Operating Systems` (DNS, TCP/TLS, reverse proxies, Linux process/disk diagnostics) |
| **Live Incident Response & Recovery** | Role Scenario | 0.20 | Outage triage, misconfigured IAM/certificates/deployments, blast-radius containment, blameless postmortems |
| **Cautiousness & Operational Discipline** | Behavioural | 0.10 | Verifying blast radius before running destructive changes; protecting production secrets/data |
| **Cross-Team Incident Communication** | Behavioural | 0.10 | Keeping developers and stakeholders aligned calmly under outage pressure |

**Representative Questions Asked in DevOps / Cloud Engineer Interviews:**
- **Resume / Project Opener**: "You containerized your web application with Docker and deployed it on AWS using a CI/CD pipeline. How did you pass production secrets into the container, and what happens right now if a broken build passes unit tests but crashes on startup?"
- **Core Technical — Fundamentals**: "Why can a naive Node.js or Python Dockerfile end up over 1.2 GB and rebuild `npm install` or `pip install` on every single code edit, and how do layer ordering and multi-stage builds solve both problems?"
  - **Hidden Reference Concepts**: Docker caches layers sequentially; copying package manifests (`package.json`/`requirements.txt`) and installing dependencies before `COPY . .` preserves dependency layer cache; multi-stage builds compile/build in a builder stage and copy only runtime artifacts into a minimal `slim`/`distroless` image, reducing size and attack surface (plus running as non-root).
- **Core Technical — Deep / Trade-Off**: "An application running in a private AWS VPC subnet suddenly fails to pull packages from an external HTTPS registry and cannot read objects from an S3 bucket in the same region. Walk through every VPC, routing, security-group/NACL, IAM, and VPC Endpoint layer you check—and why a Gateway VPC Endpoint is preferable to routing S3 traffic through a NAT Gateway."
  - **Hidden Reference Concepts**: Route table (`0.0.0.0/0` to NAT Gateway in public subnet with IGW), stateful Security Group egress vs. stateless NACL inbound/outbound ephemeral ports, IAM role policy + S3 bucket policy; Gateway S3 VPC Endpoint keeps S3 traffic on AWS private backbone at zero per-GB NAT processing cost.
- **Role Scenario**: "At 2:00 AM, alerts fire showing HTTP 502 errors spiking to 60% behind your Application Load Balancer right after an automated scaling event and config update. Disk space on two nodes is also at 99%. How do you stabilize service, isolate whether the config change or disk exhaustion is primary, and prevent recurrence?"
  - **Hidden Required Concepts**: Halt auto-rollout / revert recent config if correlated; check ALB target health checks and drain unhealthy targets; inspect `df -h` / `du` / unrotated container logs or deleted-but-open file descriptors (`lsof +L1`); add log rotation, disk saturation alerts below 80%, and canary health gates.
- **Behavioural (STAR)**: "Tell me about a time an automation script, configuration change, or deployment you worked on caused an unexpected failure—or nearly did. How did you catch or contain it, and what safeguard did you put in place?"

---

### 5. QA / Test Engineer (`qa-test-engineer`)

- **Grounding & Provenance**: Grounded in O\*NET [15-1253.00 Software Quality Assurance Analysts and Testers](https://www.onetonline.org/link/summary/15-1253.00) (identifying and documenting defects, developing regression and negative tests, designing test plans/scripts, and using Hot Technologies including Selenium, JUnit, GitLab, PostgreSQL, Spring Boot, React, and JIRA) and ESCO [software tester (ISCO 2519.6)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F106f79e4-6264-45f1-9e7a-297435cd684b&language=en) (levels of software testing, replicating customer software issues, software anomalies, unit/integration testing, and critical defect reporting).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **Coding** (writing automated test assertions, boundary-value generators, or bug-finding functions).
- **Level Expectations**:
  - **Intern / Junior**: Applies equivalence partitioning and boundary-value analysis, distinguishes unit/integration/E2E tests, writes reproducible bug reports, and scripts clean API or UI assertions in Python/JS.
  - **Mid**: Eliminates flaky E2E tests, designs contract and database-state assertions, builds risk-based regression suites inside CI pipelines, and evaluates release readiness under time pressure.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **Test Design & Quality Methodology** | Technical | 0.20 | `Test Design` (test pyramid, boundary values, equivalence partitioning, negative/exploratory testing) |
| **Test Automation & Frameworks** | Technical | 0.20 | `Test Automation` (Playwright/Selenium locators, explicit waits vs. sleeps, API contract testing, fixtures) |
| **Python / Scripting for QA** | Technical | 0.15 | `Python` (`pytest` fixtures/parametrization, mocking external services, data setup/teardown) |
| **Release Triage & Risk Prioritisation** | Role Scenario | 0.25 | Deciding what to test when time is cut before a release; diagnosing intermittent/flaky bugs |
| **Attention to Detail & Scepticism** | Behavioural | 0.10 | Questioning happy-path assumptions and uncovering subtle data-corruption edge cases |
| **Constructive Defect Advocacy** | Behavioural | 0.10 | Pushing back on risky releases diplomatically with clear evidence rather than opinion |

**Representative Questions Asked in QA / Test Engineer Interviews:**
- **Resume / Project Opener**: "In your automated test suite, what was the flakiest test you encountered—one that sometimes passed and sometimes failed without code changes—and how did you diagnose and fix it?"
- **Core Technical — Fundamentals**: "A coupon input accepts discount percentages between 5% and 50% (integers only) for cart totals above INR 500, up to 3 uses per customer. Using equivalence partitioning and boundary-value analysis, list the minimal high-signal test cases you would design, including negative cases."
  - **Hidden Reference Concepts**: Boundaries (`4, 5, 50, 51`; cart `499.99, 500.00, 500.01`; usage count `0, 3, 4`); invalid types (decimals `10.5`, negative numbers, empty/null, SQL/script strings, expired code, concurrent 3rd-use redemption).
- **Core Technical — Deep / Trade-Off**: "Why does sprinkling `time.sleep(5)` throughout UI automation tests both slow down CI and still leave tests flaky under load, and what combination of explicit condition waits, test-data isolation, and API-level setup should replace it?"
  - **Hidden Reference Concepts**: Fixed sleeps waste time when UI is fast and fail when CI runners spike above 5s; deterministic condition polling / auto-waiting on stable accessible roles/test-ids; seed state via API/DB instead of clicking through login UI on every test; isolate per-worker test users so parallel runs don't mutate shared records.
- **Role Scenario**: "A hotfix touching checkout tax calculation and promo codes must ship in 2 hours, but your full regression suite takes 90 minutes and 4 E2E tests are currently failing on an unrelated staging environment issue. What do you test, what do you skip, and what exact go/no-go evidence do you hand the release lead?"
  - **Hidden Required Concepts**: Risk-based matrix (P0 checkout, tax rounding, promo stacking, payment capture/refund, DB totals); run fast unit + API integration suites first; manually/targetedly verify changed code paths and staging failure root cause; document explicit residual risks and sign-off conditions.
- **Behavioural (STAR)**: "Tell me about a time a developer or manager wanted to close a bug as 'minor' or 'works on my machine,' and you believed it would hurt real users. How did you make your case?"
- **Practical Round (Coding)**: Write a parameterized test suite (or validator function) uncovering subtle off-by-one, timezone, and rounding bugs in a billing/discount function.

---

### 6. Data Analyst (`data-analyst`)

- **Grounding & Provenance**: Grounded in O\*NET [15-2051.01 Business Intelligence Analysts](https://www.onetonline.org/link/summary/15-2051.01) (generating custom reports for stakeholders, maintaining BI dashboards and databases, identifying business trends, and using Hot Technologies including Transact-SQL/PL-SQL/PostgreSQL, Looker, Alteryx, Power BI, SPSS/MATLAB, Google Analytics, and Git) and ESCO [data analyst (ISCO 2511.2)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Fd3edb8f8-3a06-47a0-8fb9-9b212c006aa2&language=en) (data quality assessment, query languages, visual presentation techniques, data models, and business intelligence).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **SQL** (joins, aggregations, window functions, cohort retention, deduplication).
- **Level Expectations**:
  - **Intern / Junior**: Writes accurate `LEFT JOIN`, `GROUP BY`, `HAVING`, and `CASE` queries without fan-out bugs, distinguishes mean vs. median and correlation vs. causation, and picks clear chart types.
  - **Mid**: Uses CTEs and window functions (`ROW_NUMBER`, `LAG`, rolling windows), defines unambiguous product/finance metrics, detects Simpson's paradox and selection bias, and resolves cross-team metric discrepancies.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **SQL & Analytical Querying** | Technical | 0.25 | `SQL` (joins, fan-out traps, `NULL` semantics, CTEs, window functions, query performance) |
| **Applied Statistics & Experimentation** | Technical | 0.15 | `Statistics` (distributions, outliers, confidence intervals, A/B test pitfalls, Simpson's paradox) |
| **Data Visualisation & Metric Design** | Technical | 0.15 | `Data Visualisation` (chart selection, denominator choice, funnel/cohort framing, avoiding misleading axes) |
| **Stakeholder Communication & Disputed Metrics** | Role Scenario | 0.15 | Reconciling conflicting dashboard numbers across Marketing and Finance; framing actionable recommendations |
| **Data Quality & Source Tracing** | Role Scenario | 0.15 | Investigating sudden metric drops/spikes, duplicate events, missing tracking, timezone/late-arriving rows |
| **Ownership & Analytical Integrity** | Behavioural | 0.10 | Flagging caveats honestly when data does not support a stakeholder's preferred conclusion |
| **Structured Collaboration** | Behavioural | 0.05 | Clarifying vague business questions before writing queries |

**Representative Questions Asked in Data Analyst Interviews:**
- **Resume / Project Opener**: "In your sales or customer-churn analytics project, which single metric or chart changed your conclusion the most once you cleaned the raw dataset, and what was broken in the raw data before you cleaned it?"
- **Core Technical — Fundamentals**: "You join an `orders` table (1,000 rows totaling INR 10,00,000) to an `order_items` table and an `order_discounts` table, and your `SUM(orders.total_amount)` suddenly jumps to INR 28,00,000. Why did this happen, and how do you fix the query without losing item-level or discount-level filters?"
  - **Hidden Reference Concepts**: One-to-many join fan-out (Cartesian multiplication across multiple child rows per `order_id`); pre-aggregate child tables in CTEs/subqueries keyed by `order_id` before joining, or filter with `EXISTS` instead of joining directly before `SUM`.
- **Core Technical — Deep / Trade-Off**: "Overall conversion rate on your checkout flow dropped from 5.2% last month to 4.7% this month, yet conversion rate actually increased slightly on both Desktop and Mobile when viewed separately. How is this mathematically possible, and what follow-up cuts would you run before telling leadership checkout is broken?"
  - **Hidden Reference Concepts**: Simpson's paradox driven by traffic-mix shift (e.g., a paid campaign drove a surge of lower-converting mobile traffic, shifting denominator weights); check traffic volume mix by channel/device/new-vs-returning users and absolute conversions before blaming product UX.
- **Role Scenario**: "Thirty minutes before a quarterly review, the VP of Marketing says her campaign dashboard shows 14,200 new sign-ups last month, while Finance's revenue report shows only 11,600. Both teams claim their query is right. Walk through how you audit and reconcile the gap."
  - **Hidden Required Concepts**: Compare metric definitions side-by-side (event timestamp vs. verified account vs. paid activation; UTC vs. IST timezone cutoffs; deduplication by `email` vs. `user_id`; test/internal/bot exclusions; attribution window); trace upstream source tables; publish one documented canonical metric definition.
- **Behavioural (STAR)**: "Tell me about a time you spotted an error in an analysis, report, or dataset—especially if someone had already seen the earlier numbers. How did you handle communicating the correction?"
- **Practical Round (SQL)**: Write a SQL query computing 7-day rolling retention or month-over-month revenue growth per category while deduplicating retried payment rows using `ROW_NUMBER() OVER (PARTITION BY ...)`.

---

### 7. Data Scientist / ML Engineer (`data-scientist-ml`)

- **Grounding & Provenance**: Grounded in O\*NET [15-2051.00 Data Scientists](https://www.onetonline.org/link/summary/15-2051.00) (processing large datasets, testing/validating/reformulating predictive models, presenting results to stakeholders, and using Hot Technologies including Python/PyTorch/TensorFlow, SPSS, Docker, Kubernetes, AWS EC2/Redshift/SageMaker, PostgreSQL, Airflow, Spark, and Kafka) and ESCO [data scientist (ISCO 2511.3)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F258e46f9-0075-4a2e-adae-1ff0477e0f30&language=en) (analytical mathematical calculations, data mining, data models, data quality processes, and reporting analysis results).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **Coding** (vectorized data pipelines, evaluation metrics from scratch, feature preprocessing without leakage).
- **Level Expectations**:
  - **Intern / Junior**: Prevents train/test data leakage, chooses proper metrics for imbalanced classes (PR-AUC, F1, calibration vs. accuracy), explains bias-variance, regularization, and tree vs. linear models, and writes clean Python/NumPy/pandas code.
  - **Mid**: Designs temporal/grouped cross-validation, compares against simple deterministic baselines, handles feature drift/label delay in production, optimizes inference latency/cost, and aligns offline metrics with business KPIs.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **Machine Learning Fundamentals & Evaluation** | Technical | 0.25 | `Machine Learning` (leakage, bias-variance, tree/linear/neural trade-offs, class imbalance, offline vs. online metrics) |
| **Python & Data Engineering for ML** | Technical | 0.20 | `Python` (vectorization, reproducible pipelines, complexity, serialization, API serving basics) |
| **Probability, Statistics & Experimentation** | Technical | 0.15 | `Statistics` (Bayes' rule, hypothesis testing, p-values/multiple testing, confidence intervals, calibration) |
| **Production Model Degradation & Drift** | Role Scenario | 0.20 | Diagnosing why a model with 0.92 offline ROC-AUC performs poorly in production (leakage, covariate/concept drift, serving skew) |
| **Intellectual Rigor & Baseline Honesty** | Behavioural | 0.10 | Comparing complex models fairly against simple baselines and reporting negative results honestly |
| **Translating Models for Non-ML Stakeholders** | Behavioural | 0.10 | Explaining model uncertainty, thresholds, and business trade-offs without jargon |

**Representative Questions Asked in Data Scientist / ML Engineer Interviews:**
- **Resume / Project Opener**: "In your ML project on your resume, what was the simplest non-ML or heuristic baseline you compared your model against, how did you split train and validation data, and where did your model still fail?"
- **Core Technical — Fundamentals**: "A fraud-detection dataset has 0.4% fraudulent transactions. A candidate preprocesses the entire dataset with `StandardScaler` and `SMOTE`, runs random 5-fold cross-validation, and reports 99.6% accuracy. Identify at least three methodological errors in this pipeline and how to fix each one."
  - **Hidden Reference Concepts**: (1) Fitting scaler and SMOTE before splitting leaks validation distribution/synthetic neighbors into training—fit inside each CV fold pipeline only; (2) Random k-fold leaks future fraud patterns into past transactions—use time-based split; (3) Accuracy is useless at 0.4% prevalence (predicting all-legit yields 99.6%)—use PR-AUC, recall at fixed precision/FPR, and cost-weighted threshold tuning.
- **Core Technical — Deep / Trade-Off**: "Compare L1/L2-regularized Logistic Regression, Gradient Boosted Decision Trees (XGBoost/LightGBM), and a fine-tuned Transformer when building a tabular + short-text ticket routing classifier with 15,000 labeled rows and a 30 ms CPU latency budget."
  - **Hidden Reference Concepts**: Sample efficiency on tabular + TF-IDF features; GBDT strength on heterogeneous tabular interactions and missing values; calibration and interpretability of linear models; Transformer latency/compute overhead on CPU unless distilled/cached; hybrid TF-IDF/embedding + GBDT/linear baseline first.
- **Role Scenario**: "Your loan-default model achieved 0.86 ROC-AUC on held-out historical data, but three weeks after launch in a new customer segment, default rates among approved users are twice what offline validation predicted. Walk through your diagnostic checklist."
  - **Hidden Required Concepts**: Check training-serving skew first (null/unit mismatch, broken feature pipeline in prod); check target leakage in offline eval (post-application features accidentally included); check covariate shift (new segment demographics/channel) and selection/reject-inference bias; inspect probability calibration vs. rank order; fall back to conservative rule/threshold while fixing.
- **Behavioural (STAR)**: "Tell me about a time you spent significant effort on a model, feature, or hypothesis that failed to beat the baseline. How did you decide when to stop and pivot?"
- **Practical Round (Coding)**: Implement precision, recall, F1, and ROC-AUC / confusion-matrix threshold selection from raw predicted probabilities and labels (handling ties and edge cases cleanly in Python).

---

### 8. Business Analyst (`business-analyst`)

- **Grounding & Provenance**: Grounded in O\*NET [15-1211.00 Computer Systems Analysts](https://www.onetonline.org/link/summary/15-1211.00) and [13-1111.00 Management Analysts](https://www.onetonline.org/link/summary/13-1111.00) (gathering information on business problems/procedures, linking computer systems, preparing implementation recommendations, and using Hot Technologies including SQL/PL-SQL/PostgreSQL, Tableau/Power BI, Microsoft Visio, JIRA/Confluence, Salesforce, and SAP) and ESCO [ICT business analyst (ISCO 2511.8)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Ffe0fa514-b48d-4a53-9757-a283c0baacf0&language=en) and [business analyst (ISCO 2421.1)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F60082a99-d8ef-4e84-9290-78902681b6ed&language=en) (gathering and analyzing business requirements, business process modelling, cost-benefit analysis, and risk management).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **SQL** (business funnel queries, operational reporting, cohort segmentation).
- **Level Expectations**:
  - **Intern / Junior**: Writes clear user stories with testable acceptance criteria (Given/When/Then), maps current-state ("as-is") vs. future-state ("to-be") workflows, and writes clean SQL aggregations/joins to size business problems.
  - **Mid**: Uncovers hidden non-functional and regulatory constraints, quantifies ROI/cost-benefit trade-offs, mediates conflicting departmental requirements, and designs UAT sign-off plans.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **Requirements Engineering & Acceptance Criteria** | Technical | 0.15 | `Requirements Engineering` (functional vs. non-functional requirements, edge cases, Given/When/Then, UAT) |
| **SQL & Quantitative Sizing** | Technical | 0.15 | `SQL` (aggregations, funnels, joins, cohort slicing, data validation for business cases) |
| **Process Modelling & Root-Cause Analysis** | Technical | 0.15 | `Process Modelling` (as-is vs. to-be workflows, bottleneck analysis, system handoffs, swimlanes) |
| **Resolving Conflicting Stakeholder Requirements** | Role Scenario | 0.30 | Aligning Sales, Operations, and Finance when requirements contradict; scoping MVP vs. Phase 2 |
| **Stakeholder Empathy & Active Listening** | Behavioural | 0.15 | Probing beneath surface feature requests to uncover the underlying operational problem |
| **Adaptability & Change Management** | Behavioural | 0.10 | Guiding non-technical teams through workflow changes and UAT adoption |

**Representative Questions Asked in Business Analyst Interviews:**
- **Resume / Project Opener**: "Tell me about a project or internship where a stakeholder asked for a specific report, dashboard, or feature, and once you dug into their workflow you realized they actually needed something different. How did you uncover that?"
- **Core Technical — Fundamentals**: "What is the difference between a functional requirement, a non-functional requirement, and an acceptance criterion? Rewrite the vague request 'Make customer refund approvals faster' into one crisp user story, two measurable non-functional requirements, and three Given/When/Then acceptance criteria including an exception path."
  - **Hidden Reference Concepts**: Functional (what the system does, e.g., auto-approve refunds under INR 1,000 for verified deliveries) vs. non-functional (latency, auditability, role security, uptime); testable Given/When/Then covering happy path, threshold boundary, and fraud/duplicate rejection.
- **Core Technical — Deep / Trade-Off**: "When mapping an 'as-is' order-to-cash workflow across CRM, ERP, and Support tools, how do you distinguish an automation problem from a broken policy/handoff problem—and why can automating an unstandardized process make error rates worse?"
  - **Hidden Reference Concepts**: Measure cycle time vs. wait/rework time at handoffs; inspect exception rates and manual overrides; automating ambiguous rules hard-codes edge-case failures at scale without audit visibility; standardize rules, ownership, and data schema before automation.
- **Role Scenario**: "Sales wants one-click instant onboarding with only a phone number to boost sign-ups, while Compliance/Finance insists on mandatory PAN/GST verification and manual approval before any account is created. Engineering has capacity for one unified flow this quarter. How do you facilitate alignment and propose a solution?"
  - **Hidden Required Concepts**: Quantify drop-off cost vs. regulatory/fraud exposure; separate account creation/sandbox exploration (progressive KYC) from high-risk actions (payouts/invoicing gated on automated PAN/GST verification); document edge cases, audit trail, and phased rollout agreed by both leads.
- **Behavioural (STAR)**: "Describe a situation where two stakeholders gave you contradictory instructions or priorities on the same deliverable. How did you get them to agree without simply escalating everything?"
- **Practical Round (SQL)**: Query customer onboarding and support-ticket tables to identify which onboarding step has the highest drop-off and longest resolution time by account tier.

---

### 9. Associate Product Manager (`associate-product-manager`)

- **Grounding & Provenance**: Grounded in O\*NET [15-1299.09 Information Technology Project Managers](https://www.onetonline.org/link/summary/15-1299.09) (assessing current and future customer needs, managing scope and deliverables, and using Hot Technologies including Google Analytics, Tableau, SQL, JIRA, Figma/Adobe CC, Git, and Slack) and ESCO [ICT product manager (ISCO 1330.6)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Fa79170ad-0b7b-4697-864f-1748359aa10a&language=en) (planning product management, ICT software specifications, market research, cost-benefit analysis, risk analysis, and Agile development).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **None** (Quick mode includes a Role Scenario slot alongside technical product competencies).
- **Level Expectations**:
  - **Intern / Junior**: Segments users clearly, identifies real user pain points before jumping to UI features, defines a North Star plus guardrail metric, and writes structured PRDs/user stories.
  - **Mid**: Weighs engineering effort, strategic moat, unit economics, and cannibalization risks; diagnoses funnel drops methodically; runs disciplined experiments and sprint trade-offs.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **Product Metrics & Funnel Diagnostics** | Technical | 0.20 | `Product Metrics` (North Star vs. counter/guardrail metrics, activation/retention funnels, A/B test sizing) |
| **Prioritisation & Trade-Off Frameworks** | Technical | 0.15 | `Prioritisation` (RICE/ICE limits, impact vs. effort, opportunity cost, MVP scoping, reversible vs. one-way doors) |
| **Agile Execution & PRD Clarity** | Technical | 0.10 | `Agile` (writing PRDs, acceptance criteria, sprint scope cuts, working with engineering & design) |
| **Feature Trade-Offs & Product Strategy** | Role Scenario | 0.30 | Choosing between two competing features under constrained engineering capacity; diagnosing sudden retention drops |
| **Influence Without Authority** | Behavioural | 0.15 | Aligning engineers, designers, and business leads without direct management authority |
| **Customer Curiosity & Ownership** | Behavioural | 0.10 | Grounding decisions in user research and data rather than personal preference |

**Representative Questions Asked in Associate Product Manager Interviews:**
- **Resume / Project Opener**: "Pick a product or project you built or analyzed on your resume. Who was the exact target user, what feature did you intentionally leave out of version 1, and what metric would prove version 1 actually worked?"
- **Core Technical — Fundamentals**: "You are launching a 'Quick Reorder' button in a campus food-delivery app. Define one primary success metric, two guardrail (counter) metrics, and explain why measuring 'total clicks on Quick Reorder' alone could mislead the team."
  - **Hidden Reference Concepts**: Primary metric tied to value/conversion (e.g., checkout completion rate or time-to-order for repeat users); guardrails (order cancellation/refund rate from accidental taps, average order value cannibalization, checkout error rate); raw button clicks ignore cannibalization of normal search flow and post-click abandonment.
- **Core Technical — Deep / Trade-Off**: "Where does a formulaic RICE score break down when prioritizing a technical-debt refactor or trust-and-safety fix against a shiny growth feature, and how do you structure prioritization across buckets instead?"
  - **Hidden Reference Concepts**: RICE underweights tail-risk/compliance/platform velocity compounds and suffers from subjective Reach/Confidence inflation; allocate explicit portfolio capacity buckets (core reliability/tech debt vs. strategic bets vs. incremental optimizations) and sequence dependencies.
- **Role Scenario**: "You are the APM for an online test-prep platform with 3 engineers for the next 6-week cycle. Option A is an AI doubt-solver requested in 40% of support tickets; Option B is fixing the day-1 onboarding flow where 55% of new sign-ups drop off before taking their first diagnostic quiz. How do you evaluate both options and make a recommendation?"
  - **Hidden Required Concepts**: Size reach across the funnel (55% top-of-funnel drop starves downstream features including doubt-solving vs. retention/monetization lift among active learners); check whether onboarding drop is low-effort friction vs. intent mismatch; evaluate AI inference cost/hallucination risk; propose data check + scoped MVP sequence.
- **Behavioural (STAR)**: "Tell me about a time an engineer or teammate pushed back strongly against an idea or scope you proposed. How did you respond, and what shipped in the end?"

---

### 10. Product Marketing (`product-marketing`)

- **Grounding & Provenance**: Grounded in O\*NET [13-1161.00 Market Research Analysts and Marketing Specialists](https://www.onetonline.org/link/summary/13-1161.00) (determining marketplace positioning, analyzing customer demographics/preferences/buying habits, devising survey methods, and using Hot Technologies including Looker, Tableau, SPSS, Google Ads/HubSpot/Marketo, Asana, and Slack) and ESCO [marketing manager (ISCO 1221.3.2)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F6fcf4638-e7c7-4978-9302-9a7b63a3d57c&language=en) (product marketing manager altLabel: brand/content marketing strategy, market research, customer segmentation, tracking KPIs, and coordinating launch plans).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **None** (Quick mode includes Role Scenario).
- **Level Expectations**:
  - **Intern / Junior**: Distinguishes product features from user benefits, identifies Ideal Customer Profiles (ICPs) and competitive alternatives, writes clear value propositions, and understands CAC, conversion rate, and activation funnels.
  - **Mid**: Designs tiered Go-To-Market (GTM) launches (Tier 1 vs. Tier 3), equips sales/support teams with battlecards, runs win/loss and pricing research, and attributes pipeline/adoption impact accurately.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **Positioning & Messaging Architecture** | Technical | 0.15 | `Positioning` (ICP definition, competitive alternatives, differentiated value, feature-to-benefit translation) |
| **Market & Customer Research** | Technical | 0.15 | `Market Research` (unbiased customer interviews, survey design, win/loss analysis, segmentation) |
| **GTM & Funnel Metrics** | Technical | 0.15 | `Marketing Metrics` (activation, adoption, CAC/LTV basics, email/landing-page conversion experiments, attribution limits) |
| **Go-To-Market Launch Planning** | Role Scenario | 0.30 | Designing a launch plan for a new feature across existing vs. net-new segments; responding to competitor pricing moves ([Google re:Work](https://rework.withgoogle.com/intl/en/guides/a-guide-to-structured-interviewing-for-better-hiring-practices?hl=en-US)) |
| **Cross-Functional Alignment** | Behavioural | 0.15 | Coordinating Product, Design, Sales, and Support around one launch narrative and timeline |
| **Creative Ownership & Iteration** | Behavioural | 0.10 | Testing messaging hypotheses and pivoting quickly when campaign data underperforms |

**Representative Questions Asked in Product Marketing Interviews:**
- **Resume / Project Opener**: "Tell me about a campaign, club event, product launch, or research project on your resume where you had to convince a specific audience to take action. How did you choose the core message, and how did you know which channel actually drove sign-ups?"
- **Core Technical — Fundamentals**: "What is the difference between product positioning, messaging, and a tagline? Take a technical feature like 'client-side browser webcam processing with zero video upload' and write positioning + messaging for two distinct personas: (1) a college student practicing interviews in a hostel, and (2) a university placement director."
  - **Hidden Reference Concepts**: Positioning (internal strategic frame: target segment, competitive alternative, unique capability, proof) vs. messaging (persona-specific external pillars) vs. copy/tagline; student cares about privacy/low bandwidth/no judgment; placement director cares about DPDPA/student data liability, zero storage cost, and campus-wide trust.
- **Core Technical — Deep / Trade-Off**: "Why do survey questions like 'Would you pay INR 499/month for this AI coach?' systematically overestimate willingness to pay, and what research methods or behavioral tests produce more reliable pricing and demand signals?"
  - **Hidden Reference Concepts**: Hypothetical/acquiescence bias; replace leading yes/no questions with past-behavior spend questions, Van Westendorp / Gabor-Granger / trade-off conjoint framing, or painted-door / waitlist-checkout behavioral tests.
- **Role Scenario**: "Your B2B SaaS workflow tool is launching a new automated reporting add-on in 4 weeks, and simultaneously your main competitor just made their basic reporting tier free ([Google re:Work](https://rework.withgoogle.com/intl/en/guides/a-guide-to-structured-interviewing-for-better-hiring-practices?hl=en-US)). How do you structure the launch tier, sharpen your differentiation, enable the sales team, and measure 30-day success?"
  - **Hidden Required Concepts**: Segment target accounts (existing power users vs. prospects evaluating competitor); differentiate on accuracy/compliance/time-saved rather than matching commodity free tier blindly; build sales battlecards + objection handling + in-app activation prompts; measure feature adoption, attach rate, and competitive win-rate.
- **Behavioural (STAR)**: "Describe a time a launch, event, or content piece fell short of your initial goal. How did you diagnose whether the audience, channel, or message was wrong?"

---

### 11. UI/UX Designer (`ui-ux-designer`)

- **Grounding & Provenance**: Grounded in O\*NET [15-1255.00 Web and Digital Interface Designers](https://www.onetonline.org/link/summary/15-1255.00) (identifying usability problems from testing or customer feedback, collaborating with front-end/back-end developers, creating storyboards/wireframes, and using Figma, Adobe CC, Axure RP, UserZoom, and HTML/CSS awareness) and ESCO [user interface designer (ISCO 2513.3)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F96e20037-0a25-4bf6-a25e-808d1605d890&language=en) and [user experience analyst (ISCO 2511.18)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Ffaed411a-f920-4100-86a8-b877928b429c&language=en) (qualitative user research, usability measurement, software UI design patterns, W3C/ICT accessibility standards, wireframing, and prototyping).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **None** (Quick mode includes Role Scenario).
- **Level Expectations**:
  - **Intern / Junior**: Conducts non-leading usability tests, applies visual hierarchy, spacing, and WCAG contrast/focus basics, designs empty/loading/error states, and uses Figma auto-layout and reusable components.
  - **Mid**: Structures design tokens and scalable component systems, balances user friction against business/technical constraints, synthesizes mixed qualitative + quantitative funnel evidence, and hands off developer-ready specs.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **User Research & Synthesis** | Technical | 0.20 | `User Research` (generative vs. evaluative research, non-leading task prompts, affinity mapping, sample bias) |
| **Usability, Interaction & Accessibility** | Technical | 0.15 | `Usability` (Nielsen's heuristics, cognitive load, error recovery, WCAG contrast/keyboard/screen-reader accessibility) |
| **Design Systems & Developer Handoff** | Technical | 0.15 | `Design Systems` (design tokens, component variants, responsive breakpoints, edge-case states: empty/loading/error/overflow) |
| **Evidence-Driven Redesign** | Role Scenario | 0.25 | Redesigning a broken multi-step flow after usability testing or funnel analytics reveal high confusion/drop-off |
| **Receptiveness to Critique & Iteration** | Behavioural | 0.15 | Separating personal attachment to visual work from user evidence during design reviews |
| **Design–Engineering Partnership** | Behavioural | 0.10 | Adapting designs pragmatically when engineering constraints surface mid-sprint |

**Representative Questions Asked in UI/UX Designer Interviews:**
- **Resume / Project Opener**: "Walk me through one screen or flow from your portfolio where usability feedback forced you to throw away your initial layout. What specific behaviour did users exhibit during testing, and what changed in version 2?"
- **Core Technical — Fundamentals**: "What makes a usability-test task prompt leading versus non-leading? Suppose you are testing a new 'Swap Interview Skill' button on a practice preview card—write a non-leading scenario prompt and list three behavioural signals you watch before asking follow-up questions."
  - **Hidden Reference Concepts**: Avoid using the exact UI label ("Swap") in the task prompt (e.g., say "Suppose you notice one of the planned topics isn't relevant to the job you're targeting—show me what you would do"); observe first-click hesitation, scanning path, misclicks, and whether the user understands consequences after changing it.
- **Core Technical — Deep / Trade-Off**: "When building or extending a design system, how do you decide whether a product team's new UI need should become a variant on an existing shared component, a brand-new shared component, or a local one-off pattern—and how do semantic design tokens support dark mode and WCAG AA contrast?"
  - **Hidden Reference Concepts**: Prop/variant bloat vs. fragmentation; check reuse across >=2-3 surfaces before promoting to core system; primitive tokens (`blue-600`) vs. semantic tokens (`surface-primary`, `text-muted`, `border-focus`) mapped per theme with verified 4.5:1 normal-text / 3:1 UI contrast ratios and visible focus rings.
- **Role Scenario**: "Analytics show 62% of mobile users abandon a 4-step resume-and-role setup form on Step 2, and 5 usability sessions reveal users are anxious about where their resume text goes and overwhelmed by 9 inputs on one screen. Engineering says backend endpoints cannot change this sprint. How do you redesign and validate the flow?"
  - **Hidden Required Concepts**: Progressive disclosure (require only Role + Level to preview value; make JD and Resume clearly optional collapsible steps); add inline privacy microcopy right next to the upload zone; preserve state across steps and specify loading/parse-error states; validate via rapid 5-user prototype test + step-2 completion rate.
- **Behavioural (STAR)**: "Tell me about a time engineering told you your design would take three weeks instead of three days to build. How did you compromise without sacrificing the core user experience?"

---

### 12. Operations / Project Coordinator (`operations-project-coordinator`)

- **Grounding & Provenance**: Grounded in O\*NET [13-1082.00 Project Management Specialists](https://www.onetonline.org/link/summary/13-1082.00) (communicating with stakeholders on requirements, identifying resource/schedule needs, resolving project problems, planning activities to meet deadlines, and using Hot Technologies including Asana, JIRA, Confluence, Microsoft Teams/Primavera, Salesforce, Tableau, Git, and Excel) and ESCO [project manager / project coordinator (ISCO 1219.6)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2Fbea99fea-0383-4c63-b944-70d4799de2c5&language=en) (risk analysis, conflict management, supervising daily operations, budget/resource tracking, and project metrics).
- **Levels & Practical Track**: `Intern`, `Junior`, `Mid` | Practical Track: **None** (Quick mode includes Role Scenario).
- **Level Expectations**:
  - **Intern / Junior**: Maintains accurate action trackers with single-threaded owners and due dates, maps task dependencies, flags blockers early, and writes crisp status updates.
  - **Mid**: Manages critical-path trade-offs (scope, schedule, resources), maintains RAID logs (Risks, Assumptions, Issues, Dependencies), standardizes repeatable SOPs, and resolves cross-team bottlenecks calmly.

| Competency | Type | Weight | Linked Taxonomy Skills / Topics |
|---|---|---|---|
| **Project Planning & Dependency Mapping** | Technical | 0.15 | `Project Planning` (milestones, critical path, RACI ownership, buffer estimation, handoff checklists) |
| **Agile & Operational Cadence** | Technical | 0.15 | `Agile` (standups, retrospectives, backlog hygiene, WIP limits, cycle-time tracking) |
| **Risk Tracking & SLA Management** | Technical | 0.15 | `Risk Tracking` (RAID logs, leading vs. lagging indicators, escalation triggers, vendor/external dependencies) |
| **Recovering a Slipping Deadline** | Role Scenario | 0.30 | Triaging a cross-functional launch or client deliverable that is 5 days behind schedule with a blocked dependency |
| **Dependability & Calm Under Pressure** | Behavioural | 0.15 | Keeping commitments organized and composed when multiple urgent requests collide ([O\*NET 13-1082.00](https://www.onetonline.org/link/summary/13-1082.00)) |
| **Conflict Resolution & Follow-Through** | Behavioural | 0.10 | Holding peers accountable for overdue deliverables respectfully without nagging or blame |

**Representative Questions Asked in Operations / Project Coordinator Interviews:**
- **Resume / Project Opener**: "Tell me about a multi-person project, campus fest, or internship workflow you coordinated where deliverables depended on people who did not report to you. How did you track progress and prevent last-minute surprises?"
- **Core Technical — Fundamentals**: "Explain the critical path in a project schedule and the RACI framework. Why does assigning two people as 'Accountable' for the same milestone almost always cause delays, and what is the difference between a Risk and an Issue in a RAID log?"
  - **Hidden Reference Concepts**: Critical path is the longest chain of dependent tasks with zero float determining minimum completion date; single `A` (Accountable) prevents diffused responsibility while multiple `R` (Responsible) can execute; a **Risk** is a probabilistic future event (needs likelihood, impact, mitigation/trigger) whereas an **Issue** has already occurred and needs immediate owner/resolution.
- **Core Technical — Deep / Trade-Off**: "An operational onboarding team processes 120 client requests a week, but average turnaround time has crept from 2 days to 7 days even though headcount stayed constant. How do you diagnose whether this is capacity overload, WIP thrashing, or upstream input defects?"
  - **Hidden Reference Concepts**: Little's Law (`Lead Time = WIP / Throughput`); measure time spent in active work vs. waiting for missing client info/rework loops; inspect arrival spikes, handoff queues, and ticket reopen rates before asking for headcount.
- **Role Scenario**: "A client-facing product rollout is scheduled in 10 business days. Today, the QA lead tells you testing hasn't started because Backend is 4 days late on an integration, while Marketing has already scheduled customer webinars for launch day. Walk through your exact next 24 hours."
  - **Hidden Required Concepts**: Quantify exact critical-path slip with Backend + QA; explore scope split (ship core flow on time, gate secondary integration behind flag) vs. parallelizing test prep on completed endpoints vs. moving launch date early before external invites go out; convene single decision meeting with options + trade-offs rather than forwarding panic; update RAID log and stakeholder comms plan.
- **Behavioural (STAR)**: "Describe a time when an important deliverable you were coordinating fell behind because a teammate or external partner missed their deadline. How did you handle the conversation and recover the timeline?"

---

## Priority Expansion Roles for Wave 2

Adding two expansion blueprints immediately after the starter 12 captures the fastest-growing technical tracks highlighted in Indian campus hiring ([Deloitte India 2026](https://www.deloitte.com/in/en/about/press-room/india-s-campus-talent-landscape-pivots-to-skill-based-hiring-as-86-percent-of-employers-adopt-ai-in-recruitment--deloitte-india.html)):

### 13. Data Engineer (`data-engineer`)
- **Grounding**: O\*NET [15-1243.00 Database Architects](https://www.onetonline.org/link/summary/15-1243.00) (Hot Technologies: Apache Airflow, Hive, Spark, DynamoDB, PostgreSQL, Docker, AWS CloudFormation, Git) and ESCO [data scientist / data engineer altLabel (ISCO 2511.3)](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F258e46f9-0075-4a2e-adae-1ff0477e0f30&language=en).
- **Skills & Weights**: `SQL & Data Warehousing` (0.25), `Python & ETL Pipelines` (0.20), `Distributed Systems / Orchestration (Spark, Airflow)` (0.15), **Scenario**: `Broken Nightly Pipeline / Schema Drift & Backfill` (0.20), **Behavioural**: `Ownership` (0.10) + `Data Reliability Rigor` (0.10) | Practical: **SQL**.
- **Signature Questions**: Idempotent daily Airflow backfills (preventing duplicate rows on retry); star schema vs. OBT partitioning/clustering trade-offs; scenario where an upstream microservice renames a JSON field at midnight and corrupts executive revenue tables.

### 14. Cybersecurity / Information Security Analyst (`cybersecurity-analyst`)
- **Grounding**: O\*NET [15-1212.00 Information Security Analysts](https://www.onetonline.org/link/summary/15-1212.00) (In-Demand skills: MITRE ATT&CK and eMASS; Hot Technologies: AWS, Linux/Bash, Docker, Splunk/Elasticsearch, Active Directory, BGP) and ESCO [ICT security / system administration](https://ec.europa.eu/esco/api/resource/occupation?uri=http%3A%2F%2Fdata.europa.eu%2Fesco%2Foccupation%2F9e2e6e1e-363b-4e1b-a673-7bc0f7343300&language=en).
- **Skills & Weights**: `Application & Web Security (OWASP)` (0.20), `Network & Linux Security` (0.20), `Cloud IAM & Secrets Hygiene` (0.20), **Scenario**: `Suspected Credential Leak / Phishing Incident Triage` (0.20), **Behavioural**: `Integrity & Cautiousness` (0.10) + `Calm Escalation` (0.10) | Practical: **None**.
- **Signature Questions**: SQL injection parameterization vs. WAF rules; SSRF against cloud metadata endpoints (`IMDSv2`); scenario triaging a leaked AWS access key found in a public GitHub commit (revoke/rotate, CloudTrail blast-radius audit, persistence check).

---

## Cross-Role Skill Reuse and Question-Bundle Authoring Priority

Because `interViv` keys technical bundles by `(skill, topic, difficulty)` rather than by company or role, authoring reviewed bundles for high-overlap skills multiplies coverage across the entire catalog immediately:

| Shared Taxonomy Skill | Roles Sharing This Skill (Count) | Existing Demo Bundle Status | Priority Action for Phase 3 |
|---|---|---|---|
| **SQL** | Data Analyst, Business Analyst, Backend, Full-Stack (+ Data Engineer) (**4–5 roles**) | Practical SQL exists; verify free-text SQL bundles | **P0**: Author 6 reviewed bundles (joins/fan-out, NULLs, window functions, indexing, aggregation) |
| **Python** | Backend, QA/Test, Data Scientist/ML (+ Data Engineer) (**3–4 roles**) | **Present in demo DB** | Reuse immediately; add QA (`pytest`) and ML-pipeline topic tags |
| **JavaScript** | Frontend, Full-Stack (**2 roles**) | Missing / verify | **P0**: Author 4 reviewed bundles (closures, event loop, async/AbortController, DOM/immutability) |
| **REST APIs** | Backend, Full-Stack (**2 roles**) | Missing / verify | **P0**: Author 4 reviewed bundles (idempotency, status codes, auth/JWT/CSRF, pagination/rate limits) |
| **DBMS** | Backend, Full-Stack (**2 roles**) | Partial / lexicon | **P1**: Author 4 reviewed bundles (ACID/isolation, B-tree indexes, normalization, N+1 queries) |
| **Statistics** | Data Analyst, Data Scientist/ML (**2 roles**) | Missing / verify | **P1**: Author 4 reviewed bundles (distributions, A/B testing/sample size, Simpson's paradox, Bayes) |
| **Agile** | Associate PM, Operations/Project Coordinator (**2 roles**) | **Present in demo DB** | Reuse immediately across APM and Operations Coordinator |
| **Docker & AWS** | DevOps/Cloud (+ Backend/ML optional) (**1–3 roles**) | **Present in demo DB** | Reuse immediately; supplement with `CI/CD` and `Networking` bundles |
| **React & Web Performance** | Frontend, Full-Stack (**2 roles**) | Missing / verify | **P1**: Author 4 reviewed bundles (render cycle/hooks, stale closures, Core Web Vitals, accessibility) |
| **Role-Specific Specialist Skills** | QA (`Test Design`, `Test Automation`), DS (`Machine Learning`), BA (`Requirements`, `Process Modelling`), APM (`Product Metrics`, `Prioritisation`), PMM (`Positioning`, `Market Research`), UX (`User Research`, `Usability`, `Design Systems`), Ops (`Project Planning`, `Risk Tracking`) | Missing (rely on background generation until reviewed) | **P2**: Seed 2 reviewed bundles (1 easy/medium, 1 medium/hard) per specialist skill alongside Phase 3d scenario bundles |
