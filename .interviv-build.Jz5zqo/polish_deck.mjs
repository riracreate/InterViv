import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const TMP_DIR = "/Users/praneetsharma/Downloads/mega 2 copy/.interviv-build.Jz5zqo";
const STARTER_PPTX = path.join(TMP_DIR, "template-starter.pptx");
const FINAL_PPTX = "/Users/praneetsharma/Downloads/mega 2 copy/interViv_Progress_Review_Polished.pptx";
const SOURCE_LAYOUT_DIR = path.join(TMP_DIR, "template-inspect", "layouts");
const FINAL_RENDER_DIR = path.join(TMP_DIR, "final-renders");
const FINAL_LAYOUT_DIR = path.join(TMP_DIR, "final-layout", "final");

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function sameElementIdentity(sourceElement, liveElement) {
  return (
    String(sourceElement.id) === String(liveElement.id) &&
    sourceElement.kind === liveElement.kind &&
    sourceElement.name === liveElement.name
  );
}

async function buildAnchorMap(presentation) {
  const anchorMap = new Map();
  for (let slideNo = 1; slideNo <= 15; slideNo += 1) {
    const sourceName = `source-slide-${String(slideNo).padStart(2, "0")}.layout.json`;
    const sourceLayout = JSON.parse(await fs.readFile(path.join(SOURCE_LAYOUT_DIR, sourceName), "utf8"));
    const liveBlob = await presentation.slides.getItem(slideNo - 1).export({ format: "layout" });
    const liveLayout = JSON.parse(await liveBlob.text());
    for (const sourceElement of sourceLayout.elements) {
      if (!sourceElement.aid) continue;
      let matches = liveLayout.elements.filter((liveElement) => sameElementIdentity(sourceElement, liveElement));
      if (matches.length !== 1 && sourceElement.text !== undefined) {
        matches = liveLayout.elements.filter(
          (liveElement) =>
            liveElement.kind === sourceElement.kind &&
            liveElement.name === sourceElement.name &&
            liveElement.text === sourceElement.text,
        );
      }
      if (matches.length !== 1 && sourceElement.text !== undefined) {
        matches = liveLayout.elements.filter(
          (liveElement) => liveElement.kind === sourceElement.kind && liveElement.text === sourceElement.text,
        );
      }
      if (matches.length === 1 && matches[0].aid) {
        anchorMap.set(`${slideNo}:${sourceElement.aid}`, matches[0].aid);
      }
    }
  }
  return anchorMap;
}

const presentation = await PresentationFile.importPptx(await FileBlob.load(STARTER_PPTX));
const anchorMap = await buildAnchorMap(presentation);

function resolveSource(slideNo, sourceAid) {
  const starterAid = anchorMap.get(`${slideNo}:${sourceAid}`);
  if (!starterAid) throw new Error(`No starter anchor for slide ${slideNo}, source ${sourceAid}`);
  return presentation.resolve(starterAid);
}

function replaceText(slideNo, sourceAid, oldText, newText) {
  resolveSource(slideNo, sourceAid).text.replace(oldText, newText);
}

function fillSlideNumber(slideNo, sourceAid) {
  const value = String(slideNo);
  resolveSource(slideNo, sourceAid).text.replace(value, value);
}

// Slide 1 — minimal, cleaner cover.
replaceText(1, "sh/ts7md4r2", "From Adaptive Mock Interviews to a Full Readiness Platform", "Progress Review · Phase 2");
replaceText(1, "sh/sryl4zqx", "Group C47  —  Oshan Shah  ·  Parth Tendulkar  ·  Praneet Sharma", "Group C47  ·  Oshan Shah  ·  Parth Tendulkar  ·  Praneet Sharma");
replaceText(1, "sh/fu94fe98", "Guided by Prof. Anushree Deshmukh", "Faculty guide: Prof. Anushree Deshmukh");
resolveSource(1, "sh/sryl4zqx").position = { left: 163.2, top: 456, width: 953.28, height: 36 };
resolveSource(1, "sh/fu94fe98").position = { left: 163.2, top: 496, width: 953.28, height: 28.8 };
fillSlideNumber(1, "sh/ozmd8r65");

// Slide 2 — recap once, then state the invariant.
replaceText(2, "sh/ozy1ofad", "What We Showed Last Time", "The first release covered one complete interview session");
replaceText(2, "sh/a10jqpsj", "Resume\nUpload", "Resume\nupload");
replaceText(2, "sh/r65knqtk", "Skill\nExtraction", "Skill\nextraction");
replaceText(2, "sh/9wnqhczy", "Adaptive\nSkill Questions", "Adaptive\nquestions");
replaceText(2, "sh/wjy9sry9", "3-Layer NLP\n+ ML Scoring", "3-layer NLP\nscoring");
replaceText(2, "sh/bip8jmho", "Elo\nDifficulty", "Elo\nadaptation");
replaceText(2, "sh/t8byxkn2", "Results\nDashboard", "Results\nsummary");
replaceText(2, "sh/a10jqpsj", "Upload", "upload");
replaceText(2, "sh/r65knqtk", "Extraction", "extraction");
replaceText(2, "sh/9wnqhczy", "Skill Questions", "questions");
replaceText(2, "sh/wjy9sry9", "3-Layer NLP", "3-layer NLP");
replaceText(2, "sh/wjy9sry9", "+ ML Scoring", "scoring");
replaceText(2, "sh/bip8jmho", "Difficulty", "adaptation");
replaceText(2, "sh/t8byxkn2", "Dashboard", "summary");
replaceText(2, "sh/s72xofmh", "interViv v1: resume upload → skill extraction → adaptive skill-wise questions → 3-layer NLP + ML scoring → Elo-based difficulty → results dashboard.", "v1 ended at the results screen; it did not retain progress between sessions.");
replaceText(2, "sh/65kfmpor", "Core principle carried forward", "Scoring stays deterministic");
replaceText(2, "sh/65kfmpor", "The LLM only generates questions — scoring, feedback, and difficulty are all deterministic, in-house logic.", "The LLM generates questions. In-house logic scores responses, produces feedback, and adjusts difficulty.");
fillSlideNumber(2, "sh/gbmxszmt");

// Slide 3 — a balanced cross-session comparison.
replaceText(3, "sh/d0jax03i", "From Mock-Interview Tool to Readiness Platform", "Learning now carries across interview sessions");
replaceText(3, "sh/3ah8rqlg", "THEN", "ONE SESSION");
replaceText(3, "sh/obq90bml", "A session-scoped adaptive quiz with a results dashboard.", "One adaptive interview with a results dashboard.");
replaceText(3, "sh/m5cra54z", "NOW", "PERSISTENT");
replaceText(3, "sh/n6ls3alk", "An Interview Readiness Platform:", "Persistent readiness platform:");
replaceText(3, "sh/n6ls3alk", "• Persistent accounts", "• Learner accounts");
replaceText(3, "sh/n6ls3alk", "• Persistent skill history", "• Skill history across sessions");
replaceText(3, "sh/n6ls3alk", "• Company / role-specific readiness %", "• Target-role readiness gaps");
replaceText(3, "sh/m1c3mlsn", "Deterministic-scoring identity is explicitly protected — no LLM-as-judge introduced anywhere in this expansion.", "The scoring method is unchanged: generated questions, deterministic evaluation.");
resolveSource(3, "sh/obq90bml").text.verticalAlignment = "middle";
resolveSource(3, "sh/n6ls3alk").position = { left: 687.84, top: 253, width: 510.24, height: 232 };
fillSlideNumber(3, "sh/re9g7yxo");

// Slide 4 — concise, sequential architecture labels.
replaceText(4, "sh/0ba143al", "Updated End-to-End System Workflow", "Persistent learner data connects interviews to a roadmap");
replaceText(4, "sh/ih8ju9sn", "Sign up /\nLog in", "Learner\naccount");
replaceText(4, "sh/i94r6xgz", "Upload\nResume", "Resume\nupload");
replaceText(4, "sh/x8vaxsfe", "Skill\nExtraction", "Extracted\nskills");
replaceText(4, "sh/g36tgryd", "Select target\ncompany / role", "Target\nrole");
replaceText(4, "sh/oz29krqh", "Adaptive multi-skill\ninterview\n(webcam + voice/text)", "Adaptive\ninterview");
replaceText(4, "sh/1wbapc7q", "Scoring\npipeline", "Deterministic\nscoring");
replaceText(4, "sh/et0reh8f", "Skill Graph &\nMastery update", "Skill\nhistory");
replaceText(4, "sh/ilwf69kv", "Gap\nAnalysis", "Gap\nanalysis");
replaceText(4, "sh/5ony1oj6", "Roadmap", "Study plan");
replaceText(4, "sh/wzex4z2p", "Dashboard", "Progress");
replaceText(4, "sh/ih8ju9sn", "Sign up /", "Learner");
replaceText(4, "sh/ih8ju9sn", "Log in", "account");
replaceText(4, "sh/x8vaxsfe", "Skill", "Extracted");
replaceText(4, "sh/x8vaxsfe", "Extraction", "skills");
replaceText(4, "sh/g36tgryd", "Select target", "Target");
replaceText(4, "sh/g36tgryd", "company / role", "role");
replaceText(4, "sh/oz29krqh", "Adaptive multi-skill", "Adaptive");
replaceText(4, "sh/oz29krqh", "(webcam + voice/text)", "voice · text · webcam");
replaceText(4, "sh/1wbapc7q", "Scoring", "Deterministic");
replaceText(4, "sh/1wbapc7q", "pipeline", "scoring");
replaceText(4, "sh/et0reh8f", "Skill Graph &", "Skill");
replaceText(4, "sh/et0reh8f", "Mastery update", "history");
replaceText(4, "sh/ilwf69kv", "Analysis", "analysis");
replaceText(4, "sh/xknyx4ja", "Candidate journey shown left to right — gap analysis and roadmap are new persistent, cross-session capabilities layered on top of the original single-session scoring loop.", "New in this phase: learner accounts, cross-session skill history, target-role gaps, and study plans.");
fillSlideNumber(4, "sh/mtcfypkn");

// Slide 5 — human labels first, implementation detail second.
replaceText(5, "sh/cf2tcr61", "Accounts, Persistence & Skill Graph", "Accounts and skill history make progress persistent");
replaceText(5, "sh/l4bupwny", "JWT Authentication", "Secure accounts");
replaceText(5, "sh/032tgr6d", "/auth/signup, /auth/login, /auth/me — bcrypt password hashing", "JWT authentication with bcrypt password hashing");
replaceText(5, "sh/w32dkbuh", "PostgreSQL Persistence", "Persistent storage");
replaceText(5, "sh/x4vedgvm", "SQLAlchemy + Alembic migrations; in-memory DB kept only for local/CI", "PostgreSQL via SQLAlchemy and Alembic; in-memory storage is limited to local and CI use");
replaceText(5, "sh/k7mxovud", "StudentSkillGraph", "Skill profile");
replaceText(5, "sh/58vehgvy", "Per-skill node with score, Elo, attempt count, last-practiced timestamp", "Score, Elo rating, attempts, and last-practiced date for each skill");
replaceText(5, "sh/sb6xsvu9", "ConceptMastery", "Concept mastery");
replaceText(5, "sh/tcfel0vu", "Concept-level demonstration rate — Mastered / Strong / Weak / Untested", "Mastered · Strong · Weak · Untested, based on demonstrated performance");
replaceText(5, "sh/gfi5grih", "Exposed via  GET /skill-graph/{user_id}   and   GET /mastery/{user_id}", "APIs:  GET /skill-graph/{user_id}   ·   GET /mastery/{user_id}");
fillSlideNumber(5, "sh/4ji5kbid");

// Slide 6 — label the thresholds as gap bands and keep coverage visible.
replaceText(6, "sh/zi98nu94", "Company Hiring Graph & Gap Analysis", "Role benchmarks turn skill history into measurable gaps");
replaceText(6, "sh/u1kbu1ov", "Companies: TCS, Infosys, Wipro, Amazon, Microsoft, Accenture, Google, Meta. Reference profiles for practice, not exact hiring criteria.", "Practice benchmarks for eight companies; not verified employer hiring criteria.");
replaceText(6, "sh/j6dcr65c", "Overall readiness = weighted average across tested skills only — untested skills are shown separately, never averaged as zero.", "Overall readiness averages tested required skills; untested skills remain separate, with coverage shown as tested ÷ required.");
replaceText(6, "sh/twfux0ne", "High", "High gap");
replaceText(6, "sh/dcnm98zm", "Medium", "Medium gap");
replaceText(6, "sh/qpwnet0b", "10–25", ">10 to 25");
replaceText(6, "sh/0fy5k3id", "Low", "Low gap");
replaceText(6, "sh/zep4byhs", "Untested", "Untested");
fillSlideNumber(6, "sh/1k3mhozu");

// Slide 7 — show the prioritization logic in audience-facing language.
replaceText(7, "sh/dcbud0ra", "Personalized Roadmap & Adaptive Engine 2.0", "Each roadmap targets the learner’s highest-priority gaps");
replaceText(7, "sh/ydkbm5sv", "Roadmap (7 / 14 / 30-day plans)", "Roadmap options: 7, 14, or 30 days");
replaceText(7, "sh/zedcfa9g", "Built from top 3–5 weak areas + weak/untested concepts", "Built from the top 3–5 role gaps and weak or untested concepts");
replaceText(7, "sh/baxkjqlk", "Foundations", "Fundamentals");
replaceText(7, "sh/25ojml43", "Intermediate depth", "Intermediate depth");
replaceText(7, "sh/id4ju1oz", "Application", "Applied practice");
replaceText(7, "sh/q143ylov", "Mock interviews", "Mock interviews");
replaceText(7, "sh/r2dkrq5g", "Framed as a recommendation, not a binding schedule.", "Recommended pacing; learners can adjust it.");
replaceText(7, "sh/s3ml0v61", "Adaptive Engine", "Adaptive question selection");
replaceText(7, "sh/e5o32lor", "Before: Elo-only difficulty adjustment (harder / same / easier)", "Previously: Elo adjusted question difficulty only.");
replaceText(7, "sh/p0zmlk7u", "Now:", "Selection sequence");
replaceText(7, "sh/ozq5szq9", "Check gap analysis for target role", "Start with target-role gaps");
replaceText(7, "sh/ozq5szq9", "Fall back to skill-graph weak areas", "Fall back to weak skills");
replaceText(7, "sh/ozq5szq9", "Pick weakest concept", "Select the weakest concept");
replaceText(7, "sh/ozq5szq9", "Match difficulty to current Elo", "Match difficulty to the current Elo");
replaceText(7, "sh/ozq5szq9", "Next LLM question prompt targets that concept", "Generate the next question for that concept");
fillSlideNumber(7, "sh/nyh4jupo");

// Slide 8 — accurately frame the webcam feature as an optional proxy signal.
replaceText(8, "sh/18byd4zy", "NEW CAPABILITY", "EXPERIMENTAL SIGNAL");
replaceText(8, "sh/g72x4zyd", "Real-Time Engagement Detection", "Optional facial-expression signal during interviews");
replaceText(8, "sh/tkby9kzm", "Live Webcam Capture", "Optional webcam input");
replaceText(8, "sh/sjix0zy1", "Baseline calibration step before scoring begins", "Estimates a personal baseline; the camera can remain off");
replaceText(8, "sh/o7ydoret", "face-api.js Classifier", "Client-side models");
replaceText(8, "sh/98rehwve", "TinyFaceDetector + expression model classify each frame into Low / Neutral / High engagement", "TinyFaceDetector locates a face; the expression model estimates probabilities");
replaceText(8, "sh/0jydkreh", "Logged With Every Answer", "Heuristic proxy labels");
replaceText(8, "sh/1k7edwv2", "Engagement label + confidence + delta-from-baseline recorded alongside each response", "Maps output to Low, Neutral, High, or Uncertain; no face stays null");
replaceText(8, "sh/kfixwbe1", "Client-Side & Lazy-Loaded", "Recorded for analysis");
replaceText(8, "sh/lgbepgvm", "Runs entirely client-side, loaded only when engagement detection starts", "Stores label, confidence, and baseline change; never alters answer scoring");
replaceText(8, "sh/7u5w765k", "Low Engagement", "Low proxy");
replaceText(8, "sh/5sne5wne", "Neutral Engagement", "Neutral proxy");
replaceText(8, "sh/jq5w365o", "High Engagement", "High proxy");
replaceText(8, "sh/i5wva1o3", "classified per frame", "+ Uncertain / no face");
replaceText(8, "sh/w3ed8r6x", "This was a future-work bullet in the last presentation — now implemented and live.", "Implemented in the prototype; optional and excluded from technical correctness scoring.");
for (const aid of ["sh/sjix0zy1", "sh/98rehwve", "sh/1k7edwv2", "sh/lgbepgvm"]) {
  resolveSource(8, aid).text.fontSize = 16;
}
fillSlideNumber(8, "sh/m9sb2x4v");

// Slide 9 — correct arithmetic and explain the retained blend.
replaceText(9, "sh/0b65obm9", "Semantic Similarity Upgrade", "Semantic similarity recognizes correct paraphrases");
replaceText(9, "sh/nex4jq5k", "Layer 1 (content match) previously: pure TF-IDF / keyword / bigram overlap", "Previously: TF-IDF, keyword, and bigram overlap");
replaceText(9, "sh/9gzml0nq", "Now:  0.60 × semantic cosine (all-MiniLM-L6-v2)  +  0.40 × TF-IDF", "Current blend:  0.60 × semantic cosine (all-MiniLM-L6-v2)  +  0.40 × TF-IDF");
replaceText(9, "sh/ofq5svm5", "Motivating case: paraphrased-but-correct answer", "Example: a correct paraphrase with little lexical overlap");
replaceText(9, "sh/oza1gfyh", "TF-IDF only  —  scored “Poor”", "TF-IDF similarity");
replaceText(9, "sh/3y107axw", "Semantic  —  scored “Good”", "Semantic similarity");
replaceText(9, "sh/do3id4fy", "Blend weight tuned by grid search vs. human baseline:", "Grid search against the human baseline:");
replaceText(9, "sh/do3id4fy", "grid optimum at 0.10 semantic weight (r = 0.775); production uses 0.60 (r = 0.768) — Δr = 0.006 across the grid.", "Best r = 0.7745 at 10% semantic; current 60% blend r = 0.7684 (Δ = 0.0061).");
replaceText(9, "sh/qlcjipgn", "Overall layer weighting (55 / 25 / 20) unchanged.", "The gain is below the 0.05 change threshold; overall layer weights (55 / 25 / 20) remain unchanged.");
fillSlideNumber(9, "sh/wba1cjqp");

// Slide 10 — deployment readiness, not an unsupported production claim.
replaceText(10, "sh/cbu58j2h", "Production Hardening & Updated Tech Stack", "Reliability controls prepare the platform for deployment");
replaceText(10, "sh/zelojyl8", "Production Hardening", "Deployment readiness");
replaceText(10, "sh/ydcnatkn", "Sentry error tracking (backend + frontend)", "Sentry instrumentation across backend and frontend");
replaceText(10, "sh/ydcnatkn", "Redis-backed 24-hour question cache", "24-hour Redis question cache");
replaceText(10, "sh/ydcnatkn", "LLM rate limiting + 3-attempt exponential backoff retry", "Rate limiting with up to three exponential-backoff retries");
replaceText(10, "sh/ydcnatkn", "Deterministic fallback chain (CSV bank → template)", "Deterministic fallback: CSV bank → template");
replaceText(10, "sh/ydcnatkn", "Startup warm-up for classifier / embeddings / graphs", "Startup preload for classifier, embeddings, and role graph");
replaceText(10, "sh/ydcnatkn", "Local load smoke test (10 concurrent users × 3 rounds)", "Local smoke test: 10 concurrent users × 3 rounds");
replaceText(10, "sh/l036l83y", "Tech Stack", "Technology updates");
replaceText(10, "sh/kzu5c32t", "New additions", "Added");
replaceText(10, "sh/725onyl4", "SQLAlchemy / Alembic / PostgreSQL", "PostgreSQL · SQLAlchemy · Alembic");
replaceText(10, "sh/725onyl4", "PyJWT / bcrypt", "PyJWT · bcrypt");
replaceText(10, "sh/725onyl4", "sentence-transformers + PyTorch", "sentence-transformers · PyTorch");
replaceText(10, "sh/725onyl4", "Redis", "Redis");
replaceText(10, "sh/725onyl4", "Sentry SDK", "Sentry SDK");
replaceText(10, "sh/725onyl4", "face-api.js", "face-api.js");
replaceText(10, "sh/725onyl4", "Web Speech API + faster-whisper tiny.en", "Web Speech API · faster-whisper (tiny.en)");
replaceText(10, "sh/m1cnetkj", "Carried over unchanged", "Existing");
replaceText(10, "sh/s7yt4b21", "React / Tailwind / Recharts frontend", "React · Tailwind · Recharts");
replaceText(10, "sh/s7yt4b21", "FastAPI backend", "FastAPI");
replaceText(10, "sh/s7yt4b21", "TF-IDF / NetworkX core NLP", "TF-IDF · NetworkX");
replaceText(10, "sh/q5gb21kb", "Voice stack replaced: Groq Whisper → Web Speech API + faster-whisper tiny.en", "Voice stack: Groq Whisper → Web Speech API + faster-whisper (tiny.en)");
fillSlideNumber(10, "sh/kjytkvup");

// Slide 11 — precise metric labels and a direct limitation.
replaceText(11, "sh/wbih4b6d", "Model & Classifier Validation", "Classifier accuracy is consistent on a balanced dataset");
replaceText(11, "sh/n69grmpw", "Logistic Regression answer-quality classifier trained on 891 balanced rows (297 each Good / Average / Poor).", "Dataset: 891 labeled responses — 297 each for Good, Average, and Poor.");
replaceText(11, "sh/o7ih0r6h", "Validation Accuracy", "Held-out accuracy");
replaceText(11, "sh/ofqtgnyt", "5-Fold CV Mean", "5-fold CV accuracy (mean ± SD)");
replaceText(11, "sh/9gza9sze", "Per-Class F1 Score", "Per-class F1");
replaceText(11, "sh/0b6tc3yx", "Note: this is classifier-only accuracy on a balanced dataset — not whole-system or hiring-prediction accuracy.", "Classifier-only metrics: they do not measure end-to-end interview quality or predict hiring outcomes.");
fillSlideNumber(11, "sh/k3uhcb6h");

// Slide 12 — use the documented primary human baseline and separate synthetic evidence.
replaceText(12, "sh/0f2lgnmp", "Human Validation & Automated Testing", "Human ratings align; 123 tests guard regressions");
replaceText(12, "sh/q903ad4n", "Human Baseline — Primary (n = 19, matched)", "Primary human-rated baseline (n = 30, 3 annotators)");
replaceText(12, "sh/dcbm583y", "r = 0.821", "r = 0.739");
replaceText(12, "sh/sb2lcnmd", "CI [0.585, 0.929]", "system–human correlation");
replaceText(12, "sh/b6d4f2lc", "κ = 0.752", "κ = 0.642");
replaceText(12, "sh/a543mx4r", "inter-rater agreement", "mean pairwise agreement");
replaceText(12, "sh/wvupgz6t", "68.4%", "p < 0.001");
replaceText(12, "sh/xw3q94ne", "band agreement", "for system–human r");
replaceText(12, "sh/atc7epon", "Secondary: n = 30 with 9 distractors", "Preliminary evidence only; a larger independent human study is still needed.");
replaceText(12, "sh/orapcf6h", "Persona Validation (n = 200, 4 annotators)", "Simulated-persona stress test (n = 200, 4 annotators)");
replaceText(12, "sh/9sj65kn2", "κ = 0.640\nPearson r = 0.958 (p < 0.001)", "κ = 0.640\nr = 0.958 · not human validation");
replaceText(12, "sh/0nap8f6l", "19 files  ·  46 → 118 passing tests\nacross 8 Phase-2 tasks", "123 passing tests (up from 46)\n19 files · eight Phase 2 tasks");
replaceText(12, "sh/9sj65kn2", "Pearson r = 0.958 (p < 0.001)", "r = 0.958 · not human validation");
replaceText(12, "sh/0nap8f6l", "19 files  ·  46 → 118 passing tests", "123 passing tests (up from 46)");
replaceText(12, "sh/0nap8f6l", "across 8 Phase-2 tasks", "19 files · eight Phase 2 tasks");
replaceText(12, "sh/1oj61kn6", "Representative pass cases", "Safeguards covered");
replaceText(12, "sh/gj25cry9", "Empty answer capped at 5", "Empty answer ≤ 5");
replaceText(12, "sh/uh0na1g3", "Gibberish capped at 10", "Gibberish ≤ 10");
replaceText(12, "sh/sfi58ryd", "Repetition capped at 15", "Repetition ≤ 15");
replaceText(12, "sh/6t0n6hg7", "Question-parroting capped at 25", "Question parroting ≤ 25");
replaceText(12, "sh/cbm5kbyh", "Genuine reused-vocabulary answers not falsely flagged", "Valid reused terms preserved");
for (const aid of ["sh/gj25cry9", "sh/uh0na1g3", "sh/sfi58ryd", "sh/6t0n6hg7", "sh/cbm5kbyh"]) {
  resolveSource(12, aid).text.fontSize = 14.67;
}
fillSlideNumber(12, "sh/alwbitsn");

// Slide 13 — limitations stated as evidence boundaries.
replaceText(13, "sh/q50nydsj", "HONESTY CHECK", "LIMITATIONS");
replaceText(13, "sh/bq9orito", "Limitations & Needs Verification", "What still needs validation");
replaceText(13, "sh/21gnuts7", "Company / role profiles curated from public sources — not verified against real hiring criteria", "Role profiles are practice benchmarks, not verified employer criteria");
replaceText(13, "sh/1076lobm", "No evidence yet that readiness score / roadmap predicts real interview or hiring outcomes", "No evidence yet links readiness scores or roadmaps to interview or hiring outcomes");
replaceText(13, "sh/vaxg7ulo", "Production deployment configured but not yet confirmed live (URLs, Sentry dashboard)", "Deployment is configured, but public URLs and live telemetry remain unverified");
replaceText(13, "sh/876xwfmx", "Human baseline is 19–30 real-rated answers; larger fully human-rated study still planned", "Primary human-rated baseline: 30 answers; a larger independent study is planned");
replaceText(13, "sh/lkvy103m", "Facial-expression engagement is a heuristic signal, not a validated psychological measure", "Webcam labels are heuristic facial-expression signals, not validated engagement measures");
fillSlideNumber(13, "sh/p0zyd0b6");

// Slide 14 — end on prioritized next milestones and verified evidence.
replaceText(14, "sh/xc7eds76", "WRAP-UP", "NEXT STEPS");
replaceText(14, "sh/wbydknq1", "Future Scope & Conclusion", "The core platform is built; validation comes next");
replaceText(14, "sh/jepwf2pc", "Future Scope", "Next milestones");
replaceText(14, "sh/idgvmx8r", "Larger human-rated study", "Verify public deployment and live telemetry");
replaceText(14, "sh/idgvmx8r", "Production deployment with public URLs", "Run a larger independent human-rated study");
replaceText(14, "sh/idgvmx8r", "Expand beyond 8 companies / 16 roles", "Test readiness against real interview outcomes");
replaceText(14, "sh/idgvmx8r", "Multilingual support", "Expand role and company coverage");
replaceText(14, "sh/idgvmx8r", "Recruiter / placement-cell mode", "Add multilingual and placement-cell modes");
replaceText(14, "sh/idgvmx8r", "Deeper multimodal signals (speech confidence / prosody)", "Research speech and prosody signals");
replaceText(14, "sh/kfidonqx", "Conclusion", "Where interViv stands");
replaceText(14, "sh/zi5c3y98", "interViv grew from a single-session scorer into a full Interview Readiness Platform — accounts, persistent skill tracking, gap analysis, and roadmaps — while keeping deterministic scoring fully intact.", "interViv now connects each interview to a persistent skill profile, target-role gap analysis, and study plan—while keeping scoring deterministic.");
replaceText(14, "sh/c3e1gjyd", "classifier CV 95.6%  ·  human r = 0.82 (n = 19)  ·  118 tests", "classifier CV accuracy 95.6%  ·  system–human r = 0.739 (n = 30)  ·  123 tests");
fillSlideNumber(14, "sh/4vmh0vq5");

// Slide 15 — usable bibliography and a restrained close.
replaceText(15, "sh/547mhg3m", "References & Thank You", "References");
replaceText(15, "sh/k3y5ov21", "Previously cited", "Core methods");
replaceText(15, "sh/76p4jqls", "IEEE / Springer / ACM papers on GenAI/CV mock interviews, multimodal candidate evaluation, RLHF-tuned interview LLMs, RoBERTa-based evaluation, and NLP interview-prep systems.", "Reimers & Gurevych (2019), Sentence-BERT — doi:10.18653/v1/D19-1410\nHaller et al. (2022), automated short-answer grading survey — arXiv:2204.03503");
replaceText(15, "sh/65gnqlk7", "Newly added", "Benchmarks and project evidence");
replaceText(15, "sh/t87ml0ji", "Reimers & Gurevych (2019) — Sentence-BERT\nVirtual Interviewers, Real Results — arXiv:2506.16542\nASAG survey & benchmark papers — arXiv:2204.03503, arXiv:2409.18596", "Meyer, Breuer & Fürst (2024), ASAG2024 benchmark — arXiv:2409.18596\nGomez et al. (2025), Virtual Interviewers, Real Results — arXiv:2506.16542\nProject evidence: model metadata, human-baseline report, blend-tuning report, and tests");
replaceText(15, "sh/t87ml0ji", "Reimers & Gurevych (2019) — Sentence-BERT", "Meyer, Breuer & Fürst (2024), ASAG2024 benchmark — arXiv:2409.18596");
replaceText(15, "sh/t87ml0ji", "Virtual Interviewers, Real Results — arXiv:2506.16542", "Gomez et al. (2025), Virtual Interviewers, Real Results — arXiv:2506.16542");
replaceText(15, "sh/t87ml0ji", "ASAG survey & benchmark papers — arXiv:2204.03503, arXiv:2409.18596", "Project evidence: model metadata, human-baseline report, blend-tuning report, and tests");
replaceText(15, "sh/na5476l8", "Thank You", "Thank you · Questions");
replaceText(15, "sh/m9c3e1kn", "Group C47  —  Oshan Shah  ·  Parth Tendulkar  ·  Praneet Sharma      Questions welcome", "Group C47  ·  Oshan Shah  ·  Parth Tendulkar  ·  Praneet Sharma");
fillSlideNumber(15, "sh/o7ah4nm5");

const sourcesBySlide = {
  2: ["interViv_best/README.md", "interViv_best/modules/nlp_scorer.py", "interViv_best/modules/adaptive_question_selector.py"],
  3: ["interViv_best/README.md", "interViv_best/modules/skill_graph.py", "interViv_best/modules/gap_analysis.py", "interViv_best/modules/roadmap_generator.py"],
  4: ["interViv_best/backend/main.py", "interViv_best/modules/skill_graph.py", "interViv_best/modules/gap_analysis.py", "interViv_best/modules/roadmap_generator.py"],
  5: ["interViv_best/backend/auth/security.py", "interViv_best/backend/db/sqlalchemy_models.py", "interViv_best/modules/skill_graph.py", "interViv_best/modules/concept_mastery.py"],
  6: ["interViv_best/data/company_hiring_graphs.yaml", "interViv_best/modules/gap_analysis.py"],
  7: ["interViv_best/modules/roadmap_generator.py", "interViv_best/modules/adaptive_question_selector.py"],
  8: ["interViv_best/frontend/src/lib/engagement.js", "interViv_best/frontend/src/pages/Interview.jsx"],
  9: ["interViv_best/docs/semantic_similarity_evidence.md", "interViv_best/docs/l1_blend_tuning.md", "https://aclanthology.org/D19-1410/"],
  10: ["interViv_best/docs/post_phase2_task_8.md", "interViv_best/docs/deployment.md", "interViv_best/backend/observability.py"],
  11: ["interViv_best/modules/model_metadata.json", "interViv_best/retrain_ml_model.py"],
  12: ["interViv_best/docs/human_baseline_report.md", "interViv_best/docs/human_baseline_methods.md", "interViv_best/docs/persona_validation_report.md", "interViv_best/tests/"],
  13: ["interViv_best/docs/human_baseline_methods.md", "interViv_best/docs/deployment.md", "interViv_best/frontend/src/lib/engagement.js", "interViv_best/modules/gap_analysis.py"],
  14: ["interViv_best/modules/model_metadata.json", "interViv_best/docs/human_baseline_report.md", "interViv_best/tests/"],
  15: ["https://aclanthology.org/D19-1410/", "https://arxiv.org/abs/2204.03503", "https://arxiv.org/abs/2409.18596", "https://arxiv.org/abs/2506.16542"]
};

for (const [slideNoText, sources] of Object.entries(sourcesBySlide)) {
  const slide = presentation.slides.getItem(Number(slideNoText) - 1);
  slide.speakerNotes.textFrame.setText(`[Sources]\n${sources.map((source) => `- ${source}`).join("\n")}`);
}

await fs.mkdir(FINAL_RENDER_DIR, { recursive: true });
await fs.mkdir(FINAL_LAYOUT_DIR, { recursive: true });
for (const [index, slide] of presentation.slides.items.entries()) {
  const stem = `final-slide-${String(index + 1).padStart(2, "0")}`;
  await writeBlob(path.join(FINAL_RENDER_DIR, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(FINAL_LAYOUT_DIR, `${stem}.layout.json`), await layout.text(), "utf8");
}

await writeBlob(path.join(TMP_DIR, "final-montage.webp"), await presentation.export({ format: "webp", montage: true, scale: 1 }));

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(FINAL_PPTX);
console.log(JSON.stringify({ finalPptx: FINAL_PPTX, slides: presentation.slides.items.length }, null, 2));
