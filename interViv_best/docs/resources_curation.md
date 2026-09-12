# Resources curation — 12 September 2026

Added 32 resources to the existing 19-row fixture (51 total). Existing rows, question-specific links, and the single System Design Primer entry are preserved. Categories and levels are editorial navigation labels, not measurements of course quality.

The full Resources page defaults to DSA and offers six category shortcuts plus the existing skill lookup. It requests up to 100 links per level. Embedded recommendations retain the API's default of three per level. The bounded query parameter fixes the previous API truncation, so increasing only the frontend limit cannot silently hide the new entries.

No provider API runs in the application. External content opens only after the user selects a link; there are no embedded videos, remote thumbnails, or runtime scraping. No dependencies, scoring paths, database schema, or personal data were changed.

## Destinations checked

Official/publisher pages or YouTube channel/video search records identified these destinations. For the 49-hour freeCodeCamp course and KodeKloud course, YouTube's public oEmbed endpoint additionally returned the matching title and publisher. This is destination verification, not a complete viewing/content audit or a guarantee of future availability.

The two Hello Interview items use the publisher's guide pages containing video walkthroughs; their labels reflect that. Paid extras/account requirements may apply on external sites. Marketing claims about ATS accuracy or guaranteed hiring outcomes are not endorsed.

| Category | Level | Resource |
| --- | --- | --- |
| DSA | beginner | [NeetCode — coding interview walkthroughs](https://www.youtube.com/@NeetCode) |
| DSA | beginner | [freeCodeCamp — Algorithms and Data Structures Tutorial](https://www.youtube.com/watch?v=8hly31xKli0) |
| DSA | intermediate | [freeCodeCamp — Data Structures and Algorithms Mega Course (49 hours)](https://www.youtube.com/watch?v=xwI5OBEnsZU) |
| DSA | beginner | [Data Structures and Algorithms in 15 Minutes](https://www.youtube.com/watch?v=oz9cEqFynHU) |
| DSA | beginner | [Striver's A2Z DSA Sheet — structured practice](https://takeuforward.org/dsa/strivers-a2z-sheet-learn-dsa-a-to-z) |
| DSA | intermediate | [NeetCode Practice — Blind 75 and NeetCode 150](https://neetcode.io/practice) |
| DSA | beginner | [GeeksforGeeks — DSA Tutorial](https://www.geeksforgeeks.org/dsa/dsa-tutorial-learn-data-structures-and-algorithms/) |
| DSA | intermediate | [Tech Interview Handbook — interview preparation guide](https://www.techinterviewhandbook.org/) |
| System Design | beginner | [ByteByteGo — system design explainers](https://www.youtube.com/@ByteByteGo) |
| System Design | intermediate | [Gaurav Sen — system design walkthroughs](https://www.youtube.com/@gkcs) |
| System Design | beginner | [Hello Interview — Design Bitly (guide and video walkthrough)](https://www.hellointerview.com/learn/system-design/problem-breakdowns/bitly) |
| System Design | advanced | [Hello Interview — Design YouTube (guide and video walkthrough)](https://www.hellointerview.com/learn/system-design/problem-breakdowns/youtube) |
| System Design | beginner | [KodeKloud — System Design for Beginners (2026)](https://www.youtube.com/watch?v=SE2KF-vxvS0) |
| Behavioral | intermediate | [Exponent — mock interviews and behavioral preparation](https://www.youtube.com/@tryexponent) |
| Behavioral | beginner | [UCL CareersLab — Interview Skills: STAR Technique](https://www.youtube.com/watch?v=p56ZvaoU7FQ) |
| Behavioral | intermediate | [Tech Interview Handbook — behavioral interview preparation](https://www.techinterviewhandbook.org/behavioral-interview/) |
| Behavioral | beginner | [Salesforce — Use the STAR Method to Ace Your Next Job Interview](https://www.salesforce.com/blog/use-the-star-method-to-ace-your-next-job-interview/) |
| SQL | advanced | [Quest2Offer — 10 senior SQL interview questions](https://www.youtube.com/watch?v=G3ze2AVOaB0) |
| SQL | beginner | [SQLBolt — interactive SQL lessons](https://sqlbolt.com/) |
| SQL | beginner | [Select Star SQL — an interactive SQL book](https://selectstarsql.com/) |
| SQL | intermediate | [HackerRank — SQL practice challenges](https://www.hackerrank.com/domains/sql) |
| SQL | beginner | [W3Schools — SQL Tutorial](https://www.w3schools.com/sql/) |
| SQL | beginner | [ThoughtSpot — SQL Tutorial](https://www.thoughtspot.com/sql-tutorial) |
| OA / MCQ | beginner | [Mark Benliyan — Cracking the Coding Assessment for Software Engineers](https://www.youtube.com/watch?v=N2QsXu_aKG4) |
| OA / MCQ | beginner | [Amazon SDE Online Assessment Guide](https://www.youtube.com/watch?v=2-s7b3HmnAQ) |
| OA / MCQ | intermediate | [Grind 75 — customize your coding practice plan](https://www.techinterviewhandbook.org/grind75/) |
| OA / MCQ | intermediate | [LeetCode — problem set](https://leetcode.com/problemset/) |
| OA / MCQ | intermediate | [HackerRank — algorithm challenges](https://www.hackerrank.com/domains/algorithms) |
| Resume / ATS | beginner | [Jobscan — How to Make an ATS-Friendly Resume in 2026](https://www.youtube.com/watch?v=Bon1BvjL7N0) |
| Resume / ATS | beginner | [Tech Interview Handbook — software engineer resume guide](https://www.techinterviewhandbook.org/resume/) |
| Resume / ATS | beginner | [Jake's Resume — LaTeX template](https://github.com/jakegut/resume) |
| Resume / ATS | intermediate | [ATS Screener — open-source resume checking tool](https://ats-screener.vercel.app/) |

## Omitted pending exact URLs

The supplied research note contained titles without URLs. These five could not be matched confidently to an original destination, so no guessed links or search-result links were added:

- How to Ace Behavioral Interviews Using the STAR Method
- 15 SQL Interview Queries You Must Know
- SQL Full Course: 10-Min Crash Course Before Your Interview
- Why Your Resume Gets Auto-Rejected | Reverse-Engineer the ATS
- Software Engineer Resume Guide (Blind)

The short DSA revision item uses the verified title “Data Structures and Algorithms in 15 Minutes”; the note's “Full Visual Course” subtitle was not carried over. The System Design Primer was already present and was not added again.

## Verification

Resource API tests (offline, memory DB):

```text
.venv/bin/python -m pytest tests/test_learning_resources.py -q -p no:cacheprovider
8 passed, 1 skipped in 4.08s
```

The skipped test requires DATABASE_URL for its unique-constraint check. A separate temporary SQLite database check created the existing schema, seeded twice, and verified all six categories:

```text
PASS SQL category DSA: 11 resources
PASS SQL category System Design: 7 resources
PASS SQL category Behavioral: 4 resources
PASS SQL category SQL: 6 resources
PASS SQL category OA / MCQ: 5 resources
PASS SQL category Resume / ATS: 4 resources
PASS SQL seed repeated twice: 51 rows, no duplicates
```

Frontend checks:

```text
node --test tests/resourceList.test.js
# tests 3
# pass 3
# fail 0

npm --offline run build
✓ 3911 modules transformed.
✓ built in 3m 12s
```

The production build retains its existing large-chunk warning for Monaco/face-api assets. The broader frontend suite did not pass:

```text
npm --offline test
# tests 54
# pass 53
# fail 1
not ok 9 - tests/interviewMediaGate.test.js
Error: Build failed with 7 errors:
src/lib/codingEditor.js:1:24: ERROR: Could not resolve "monaco-editor/esm/vs/editor/editor.api"
```

Additional errors concern the same editor's Python/Java/C++/TypeScript and worker imports. The interview test, codingEditor.js, and package.json are unchanged from base 548011f. This Resources change does not address that test bundling failure. The full backend/scoring suites were not run: no scoring code changed.

An isolated backend on 127.0.0.1:18002 returned HTTP 200 for all six categories, with the same counts as SQLite. A disposable account was used; no user account or existing database was changed. In the browser at 127.0.0.1:5175, all six category buttons loaded their corresponding lists, and DSA visibly included all 11 entries. An initial Resume/ATS navigation displayed “Failed to fetch”; the server remained healthy, its CORS preflight returned 200, and retrying the category succeeded without a code change. Its cause was not established.

The app on port 5173 was not changed. This preview uses the newer coding worktree on branch codex/resources-curation. Preview servers bind to loopback only; model/data services retain offline settings.
