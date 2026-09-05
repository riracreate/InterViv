"""Phase 2.1 Verbal Ability practice bank: 30 original MCQs.

All questions, options, explanations, and passages below were authored
originally for this repository. No upstream question bank was copied or
paraphrased; see docs/phase21_verbal_attribution.md for the authorship
record and per-question review table.

Distribution (6 groups x 5; each group 2 easy / 2 medium / 1 hard):

- vocabulary (synonyms and antonyms):      mcq_verbal_001-005
- grammar (sentence correction):           mcq_verbal_006-010
- completion (sentence completion/cloze):  mcq_verbal_011-015
- comprehension (reading comprehension):   mcq_verbal_016-020
- ordering (sentence ordering):            mcq_verbal_021-025
- idioms (idioms and contextual usage):    mcq_verbal_026-030

Total: 12 easy, 12 medium, 6 hard. Correct-option positions are
balanced across a-d (8/7/8/7). Each explanation states why the key is
right and why each distractor fails. Comprehension stems embed the full
original passage; no passage-group engine is required.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.sqlalchemy_models import MCQQuestionRow, SkillRow

VERBAL_SKILL = "Verbal Ability"

PHASE21_VERBAL_BANK: list[dict[str, Any]] = [
    # --- Vocabulary: synonyms and antonyms (001-005) ---
    {
        "id": "mcq_verbal_001",
        "skill": "Verbal Ability",
        "sub_domain": "vocabulary",
        "difficulty": "easy",
        "stem": "Choose the word closest in meaning to \"concise\".",
        "options_json": [
            {"id": "a", "text": "wordy"},
            {"id": "b", "text": "brief"},
            {"id": "c", "text": "vague"},
            {"id": "d", "text": "lengthy"},
        ],
        "correct_option_ids": ["b"],
        "explanation": "Concise means expressing much in few words, so brief (b) is the "
                       "closest match. Wordy (a) and lengthy (d) describe the opposite quality, "
                       "and vague (c) concerns clarity rather than brevity.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_002",
        "skill": "Verbal Ability",
        "sub_domain": "vocabulary",
        "difficulty": "easy",
        "stem": "Choose the word most opposite in meaning to \"expand\".",
        "options_json": [
            {"id": "a", "text": "enlarge"},
            {"id": "b", "text": "extend"},
            {"id": "c", "text": "contract"},
            {"id": "d", "text": "inflate"},
        ],
        "correct_option_ids": ["c"],
        "explanation": "Expand means to grow larger; contract (c) means to shrink, which is its "
                       "direct opposite. Enlarge (a), extend (b), and inflate (d) are all "
                       "synonyms of expand, not opposites.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_003",
        "skill": "Verbal Ability",
        "sub_domain": "vocabulary",
        "difficulty": "medium",
        "stem": "Choose the word closest in meaning to \"meticulous\".",
        "options_json": [
            {"id": "a", "text": "thorough"},
            {"id": "b", "text": "hasty"},
            {"id": "c", "text": "careless"},
            {"id": "d", "text": "indifferent"},
        ],
        "correct_option_ids": ["a"],
        "explanation": "Meticulous means showing great attention to detail, matching thorough (a). "
                       "Hasty (b) and careless (c) describe the opposite approach to work, and "
                       "indifferent (d) describes lack of interest rather than lack of care.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_004",
        "skill": "Verbal Ability",
        "sub_domain": "vocabulary",
        "difficulty": "medium",
        "stem": "Choose the word most opposite in meaning to \"transparent\".",
        "options_json": [
            {"id": "a", "text": "obvious"},
            {"id": "b", "text": "clear"},
            {"id": "c", "text": "direct"},
            {"id": "d", "text": "opaque"},
        ],
        "correct_option_ids": ["d"],
        "explanation": "Transparent means see-through or open; opaque (d) means impossible to see "
                       "through or understand, its direct opposite. Obvious (a), clear (b), and "
                       "direct (c) all point the same way as transparent rather than against it.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_005",
        "skill": "Verbal Ability",
        "sub_domain": "vocabulary",
        "difficulty": "hard",
        "stem": "Choose the word closest in meaning to \"laconic\".",
        "options_json": [
            {"id": "a", "text": "concise"},
            {"id": "b", "text": "talkative"},
            {"id": "c", "text": "blunt"},
            {"id": "d", "text": "vague"},
        ],
        "correct_option_ids": ["a"],
        "explanation": "Laconic means using very few words in speech, matching concise (a). "
                       "Talkative (b) is its opposite. Blunt (c) describes directness of manner, "
                       "not brevity, and vague (d) describes lack of clarity, not lack of words.",
        "negative_marking": 0.25,
    },
    # --- Grammar: sentence correction (006-010) ---
    {
        "id": "mcq_verbal_006",
        "skill": "Verbal Ability",
        "sub_domain": "grammar",
        "difficulty": "easy",
        "stem": "Choose the grammatically correct sentence.",
        "options_json": [
            {"id": "a", "text": "She go to school every day."},
            {"id": "b", "text": "She going to school every day."},
            {"id": "c", "text": "She goes to school every day."},
            {"id": "d", "text": "She gone to school every day."},
        ],
        "correct_option_ids": ["c"],
        "explanation": "The third-person singular subject 'She' requires 'goes' (c) in the simple "
                       "present. Option (a) uses the base form, (b) lacks a helping verb, and (d) "
                       "uses a past participle without an auxiliary.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_007",
        "skill": "Verbal Ability",
        "sub_domain": "grammar",
        "difficulty": "easy",
        "stem": "Which sentence is grammatically correct?",
        "options_json": [
            {"id": "a", "text": "He bought two new book."},
            {"id": "b", "text": "He bought two new bookes."},
            {"id": "c", "text": "He bought two new book's."},
            {"id": "d", "text": "He bought two new books."},
        ],
        "correct_option_ids": ["d"],
        "explanation": "After 'two', the countable noun must be a plain plural: 'books' (d). "
                       "Option (a) uses the singular, (b) misspells the plural, and (c) uses a "
                       "possessive apostrophe, which never forms a plural.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_008",
        "skill": "Verbal Ability",
        "sub_domain": "grammar",
        "difficulty": "medium",
        "stem": "Select the grammatically correct sentence.",
        "options_json": [
            {"id": "a", "text": "By the time we arrived, the meeting had already started."},
            {"id": "b", "text": "By the time we arrived, the meeting has already started."},
            {"id": "c", "text": "By the time we arrived, the meeting already starts."},
            {"id": "d", "text": "By the time we arrive, the meeting had already started."},
        ],
        "correct_option_ids": ["a"],
        "explanation": "An event completed before a past moment takes the past perfect: 'had "
                       "started' (a). Option (b) mixes the present perfect with a past time "
                       "marker, (c) uses the present tense, and (d) pairs a present arrival with "
                       "a past-perfect start, scrambling the sequence.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_009",
        "skill": "Verbal Ability",
        "sub_domain": "grammar",
        "difficulty": "medium",
        "stem": "Identify the grammatically correct sentence.",
        "options_json": [
            {"id": "a", "text": "She enjoys reading, swimming, and to cycle."},
            {"id": "b", "text": "She enjoys reading, swimming, and cycling."},
            {"id": "c", "text": "She enjoys to read, swimming, and cycling."},
            {"id": "d", "text": "She enjoys reading, to swim, and cycling."},
        ],
        "correct_option_ids": ["b"],
        "explanation": "Items in a list must share the same form (parallelism): three gerunds in "
                       "(b). Each of (a), (c), and (d) breaks the pattern by mixing an infinitive "
                       "('to cycle', 'to read', 'to swim') with gerunds.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_010",
        "skill": "Verbal Ability",
        "sub_domain": "grammar",
        "difficulty": "hard",
        "stem": "Which of the following sentences is grammatically correct?",
        "options_json": [
            {"id": "a", "text": "Walking through the park, the birds sang loudly."},
            {"id": "b", "text": "While walking through the park, the songs of birds filled the air."},
            {"id": "c", "text": "Walking through the park, loudly the birds sang."},
            {"id": "d", "text": "Walking through the park, I heard the birds sing loudly."},
        ],
        "correct_option_ids": ["d"],
        "explanation": "An opening participle phrase must modify the subject. Only (d) supplies a "
                       "subject ('I') who is walking. In (a) and (c) the birds are absurdly cast as "
                       "the walkers, and in (b) the songs cannot walk either.",
        "negative_marking": 0.25,
    },
    # --- Completion: sentence completion and cloze (011-015) ---
    {
        "id": "mcq_verbal_011",
        "skill": "Verbal Ability",
        "sub_domain": "completion",
        "difficulty": "easy",
        "stem": "Choose the word that best completes the sentence: The library was so ___ that even a whisper echoed.",
        "options_json": [
            {"id": "a", "text": "silent"},
            {"id": "b", "text": "noisy"},
            {"id": "c", "text": "crowded"},
            {"id": "d", "text": "bright"},
        ],
        "correct_option_ids": ["a"],
        "explanation": "Only a silent (a) room makes a whisper echo. Noisy (b) and crowded (c) "
                       "contradict the echo clue, and bright (d) concerns light, which is "
                       "irrelevant to sound.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_012",
        "skill": "Verbal Ability",
        "sub_domain": "completion",
        "difficulty": "easy",
        "stem": "Choose the word that best completes the sentence: She studied every evening, ___ she passed the examination with ease.",
        "options_json": [
            {"id": "a", "text": "yet"},
            {"id": "b", "text": "or"},
            {"id": "c", "text": "so"},
            {"id": "d", "text": "but"},
        ],
        "correct_option_ids": ["c"],
        "explanation": "Passing with ease is the result of steady study, so the result connector "
                       "'so' (c) fits. 'Yet' (a) and 'but' (d) signal a contrast that is absent, "
                       "and 'or' (b) offers an alternative that makes no sense here.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_013",
        "skill": "Verbal Ability",
        "sub_domain": "completion",
        "difficulty": "medium",
        "stem": "Choose the pair that best completes the sentence: The manager's ___ response suggested he had already made up his mind, leaving no room for further ___.",
        "options_json": [
            {"id": "a", "text": "hesitant … discussion"},
            {"id": "b", "text": "curt … debate"},
            {"id": "c", "text": "lengthy … silence"},
            {"id": "d", "text": "warm … agreement"},
        ],
        "correct_option_ids": ["b"],
        "explanation": "A curt (brusquely brief) response (b) fits a decided manager closing off "
                       "debate. Hesitant (a) implies he is undecided, contradicting the sentence. "
                       "Lengthy … silence (c) pairs contradictorily, and warm … agreement (d) "
                       "contradicts 'no room for further'.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_014",
        "skill": "Verbal Ability",
        "sub_domain": "completion",
        "difficulty": "medium",
        "stem": "Choose the word that best completes the sentence: The committee arrived ___ a decision after hours of deliberation.",
        "options_json": [
            {"id": "a", "text": "at"},
            {"id": "b", "text": "to"},
            {"id": "c", "text": "on"},
            {"id": "d", "text": "for"},
        ],
        "correct_option_ids": ["a"],
        "explanation": "The standard collocation is 'arrive at a decision' (a). 'Arrive to' (b) is "
                       "ungrammatical with this object, 'arrive on' (c) suits times rather than "
                       "decisions, and 'arrive for' (d) expresses purpose, not conclusion.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_015",
        "skill": "Verbal Ability",
        "sub_domain": "completion",
        "difficulty": "hard",
        "stem": "Choose the word that best completes the sentence: Her argument was so ___ that even her opponents conceded the point.",
        "options_json": [
            {"id": "a", "text": "controversial"},
            {"id": "b", "text": "verbose"},
            {"id": "c", "text": "tentative"},
            {"id": "d", "text": "cogent"},
        ],
        "correct_option_ids": ["d"],
        "explanation": "Opponents concede only to a convincing case, and cogent (d) means "
                       "clear and convincing. A controversial (a) argument would harden opposition, "
                       "a verbose (b) one merely runs long, and a tentative (c) one is too weak to "
                       "persuade anyone.",
        "negative_marking": 0.25,
    },
    # --- Comprehension: reading comprehension (016-020) ---
    {
        "id": "mcq_verbal_016",
        "skill": "Verbal Ability",
        "sub_domain": "comprehension",
        "difficulty": "easy",
        "stem": "Read the passage and answer the question.\n\nPassage: Every spring, the Maple "
                "Street library lends out more than books. Since 2019, its seed library has allowed "
                "cardholders to borrow small packets of vegetable and flower seeds at no cost. "
                "Borrowers plant the seeds at home and, at the end of the season, return a portion "
                "of the seeds they harvested so the stock can be replenished for the following year. "
                "The program began with forty packets donated by a local nursery and now circulates "
                "more than six hundred packets each season. Librarian Ana Reyes says the most "
                "borrowed seeds are tomatoes, beans, and sunflowers. The only rule is that borrowers "
                "must hold a valid library card; no gardening experience is required.\n\nQuestion: "
                "According to the passage, what must a borrower hold to use the seed library?",
        "options_json": [
            {"id": "a", "text": "A gardening certificate"},
            {"id": "b", "text": "A valid library card"},
            {"id": "c", "text": "A nursery membership"},
            {"id": "d", "text": "A volunteer badge"},
        ],
        "correct_option_ids": ["b"],
        "explanation": "The passage states the only rule is holding 'a valid library card' (b). A "
                       "gardening certificate (a) is explicitly ruled out ('no gardening experience "
                       "is required'), and neither a nursery membership (c) nor a volunteer badge "
                       "(d) is mentioned anywhere.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_017",
        "skill": "Verbal Ability",
        "sub_domain": "comprehension",
        "difficulty": "easy",
        "stem": "Read the passage and answer the question.\n\nPassage: Every spring, the Maple "
                "Street library lends out more than books. Since 2019, its seed library has allowed "
                "cardholders to borrow small packets of vegetable and flower seeds at no cost. "
                "Borrowers plant the seeds at home and, at the end of the season, return a portion "
                "of the seeds they harvested so the stock can be replenished for the following year. "
                "The program began with forty packets donated by a local nursery and now circulates "
                "more than six hundred packets each season. Librarian Ana Reyes says the most "
                "borrowed seeds are tomatoes, beans, and sunflowers. The only rule is that borrowers "
                "must hold a valid library card; no gardening experience is required.\n\nQuestion: "
                "The seed library began with forty packets that came from…",
        "options_json": [
            {"id": "a", "text": "the city council"},
            {"id": "b", "text": "library fines"},
            {"id": "c", "text": "a local nursery"},
            {"id": "d", "text": "the borrowers"},
        ],
        "correct_option_ids": ["c"],
        "explanation": "The passage says the forty starting packets were 'donated by a local "
                       "nursery' (c). The city council (a) and library fines (b) never appear, and "
                       "borrowers (d) return seeds later — they did not supply the original stock.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_018",
        "skill": "Verbal Ability",
        "sub_domain": "comprehension",
        "difficulty": "medium",
        "stem": "Read the passage and answer the question.\n\nPassage: Every spring, the Maple "
                "Street library lends out more than books. Since 2019, its seed library has allowed "
                "cardholders to borrow small packets of vegetable and flower seeds at no cost. "
                "Borrowers plant the seeds at home and, at the end of the season, return a portion "
                "of the seeds they harvested so the stock can be replenished for the following year. "
                "The program began with forty packets donated by a local nursery and now circulates "
                "more than six hundred packets each season. Librarian Ana Reyes says the most "
                "borrowed seeds are tomatoes, beans, and sunflowers. The only rule is that borrowers "
                "must hold a valid library card; no gardening experience is required.\n\nQuestion: "
                "What does the passage suggest about the program's growth?",
        "options_json": [
            {"id": "a", "text": "It has expanded far beyond its original stock."},
            {"id": "b", "text": "It now serves only experienced gardeners."},
            {"id": "c", "text": "It charges a fee for rare seeds."},
            {"id": "d", "text": "It lends more seeds than books."},
        ],
        "correct_option_ids": ["a"],
        "explanation": "Growth from forty packets to more than six hundred (a) is stated directly. "
                       "Option (b) contradicts 'no gardening experience is required', (c) contradicts "
                       "'at no cost', and (d) misreads 'more than books' (books plus seeds) as a "
                       "quantity comparison the passage never makes.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_019",
        "skill": "Verbal Ability",
        "sub_domain": "comprehension",
        "difficulty": "medium",
        "stem": "Read the passage and answer the question.\n\nPassage: When the office tower on "
                "Fifth Avenue installed beehives on its roof in 2021, the building's managers "
                "expected complaints. Instead, the hives became the tenants' favorite amenity. A "
                "local beekeeper visits every fortnight to inspect the colonies, and jars of honey "
                "harvested from the roof are distributed to office workers each autumn. The managers "
                "report that the hives cost less per year than the lobby's flower arrangements, while "
                "a tenant survey found that three-quarters of respondents considered the bees a "
                "positive addition. Two tenants did report stings, both after disturbing the hives "
                "during maintenance work. Encouraged by the results, the management company plans to "
                "install hives on three further buildings next year.\n\nQuestion: According to the "
                "passage, how did tenants generally respond to the hives?",
        "options_json": [
            {"id": "a", "text": "Most demanded their removal."},
            {"id": "b", "text": "Most were unaware of them."},
            {"id": "c", "text": "Most complained about the cost."},
            {"id": "d", "text": "Most considered them a positive addition."},
        ],
        "correct_option_ids": ["d"],
        "explanation": "Three-quarters of surveyed tenants called the bees a positive addition (d). "
                       "Removal demands (a) never happened — managers merely expected complaints. "
                       "Unawareness (b) is ruled out by the survey itself, and cost complaints (c) "
                       "contradict the passage's low-cost comparison.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_020",
        "skill": "Verbal Ability",
        "sub_domain": "comprehension",
        "difficulty": "hard",
        "stem": "Read the passage and answer the question.\n\nPassage: When the office tower on "
                "Fifth Avenue installed beehives on its roof in 2021, the building's managers "
                "expected complaints. Instead, the hives became the tenants' favorite amenity. A "
                "local beekeeper visits every fortnight to inspect the colonies, and jars of honey "
                "harvested from the roof are distributed to office workers each autumn. The managers "
                "report that the hives cost less per year than the lobby's flower arrangements, while "
                "a tenant survey found that three-quarters of respondents considered the bees a "
                "positive addition. Two tenants did report stings, both after disturbing the hives "
                "during maintenance work. Encouraged by the results, the management company plans to "
                "install hives on three further buildings next year.\n\nQuestion: Which statement is "
                "best supported by the passage?",
        "options_json": [
            {"id": "a", "text": "The hives eliminated the building's landscaping costs."},
            {"id": "b", "text": "The beekeeper visits the roof every week."},
            {"id": "c", "text": "The management company considers the project a success."},
            {"id": "d", "text": "Tenants harvest the honey themselves."},
        ],
        "correct_option_ids": ["c"],
        "explanation": "Low cost, a strongly positive survey, and expansion to three more buildings "
                       "together support (c). Option (a) overstates 'cost less than the flowers' as "
                       "elimination, (b) misstates 'every fortnight' as weekly, and (d) contradicts "
                       "the passage — a beekeeper tends the hives and jars are distributed.",
        "negative_marking": 0.25,
    },
    # --- Ordering: sentence ordering (021-025) ---
    {
        "id": "mcq_verbal_021",
        "skill": "Verbal Ability",
        "sub_domain": "ordering",
        "difficulty": "easy",
        "stem": "Arrange the sentences into the most coherent paragraph. S1: Maya decided to bake "
                "bread for the first time. S2: She mixed flour, water, and yeast in a large bowl. "
                "S3: After the dough rose for an hour, she shaped it into loaves. S4: By evening, "
                "the kitchen smelled of fresh bread.",
        "options_json": [
            {"id": "a", "text": "S1, S2, S3, S4"},
            {"id": "b", "text": "S2, S1, S4, S3"},
            {"id": "c", "text": "S1, S3, S2, S4"},
            {"id": "d", "text": "S3, S2, S1, S4"},
        ],
        "correct_option_ids": ["a"],
        "explanation": "Only (a) preserves the time chain: decision (S1), mixing (S2), rising and "
                       "shaping (S3), finished bread by evening (S4). Option (b) mixes before Maya "
                       "decides, (c) rises the dough before it is mixed, and (d) starts mid-process "
                       "with the rising.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_022",
        "skill": "Verbal Ability",
        "sub_domain": "ordering",
        "difficulty": "easy",
        "stem": "Arrange the sentences into the most coherent paragraph. S1: The school announced "
                "a science fair in March. S2: Ravi chose to build a model volcano. S3: He spent two "
                "weeks painting it and wiring the lights. S4: On the day of the fair, his volcano "
                "won second prize.",
        "options_json": [
            {"id": "a", "text": "S2, S1, S3, S4"},
            {"id": "b", "text": "S1, S2, S3, S4"},
            {"id": "c", "text": "S1, S2, S4, S3"},
            {"id": "d", "text": "S4, S3, S2, S1"},
        ],
        "correct_option_ids": ["b"],
        "explanation": "Announcement (S1) precedes the choice (S2), the two weeks of building (S3), "
                       "and finally the fair day (S4). Option (a) chooses before the announcement, "
                       "(c) awards the prize before the model is built, and (d) runs the whole "
                       "story backwards.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_023",
        "skill": "Verbal Ability",
        "sub_domain": "ordering",
        "difficulty": "medium",
        "stem": "Arrange the sentences into the most coherent paragraph. S1: Cities depend on "
                "delivery trucks, but the trucks clog narrow streets. S2: To ease congestion, "
                "several cities now restrict daytime deliveries. S3: These restrictions push freight "
                "companies toward night schedules. S4: Residents, however, complain about the noise "
                "of midnight unloading.",
        "options_json": [
            {"id": "a", "text": "S2, S1, S3, S4"},
            {"id": "b", "text": "S1, S3, S2, S4"},
            {"id": "c", "text": "S1, S2, S3, S4"},
            {"id": "d", "text": "S3, S2, S1, S4"},
        ],
        "correct_option_ids": ["c"],
        "explanation": "S1 states the problem, S2 answers it ('To ease congestion'), S3 follows with "
                       "'These restrictions', and S4 contrasts the outcome with 'however'. In (b) S3 "
                       "refers to restrictions before any are introduced; (a) and (d) open with "
                       "sentences whose references ('congestion', 'These restrictions') have no "
                       "antecedent.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_024",
        "skill": "Verbal Ability",
        "sub_domain": "ordering",
        "difficulty": "medium",
        "stem": "Arrange the sentences into the most coherent paragraph. S1: Tea was first carried "
                "to Europe by Dutch traders in the 1600s. S2: At first, it was sold mainly as a "
                "medicine. S3: Over time, coffee houses began serving it as a fashionable drink. S4: "
                "By the 1700s, tea-drinking had become an English ritual.",
        "options_json": [
            {"id": "a", "text": "S1, S3, S2, S4"},
            {"id": "b", "text": "S2, S1, S4, S3"},
            {"id": "c", "text": "S4, S1, S2, S3"},
            {"id": "d", "text": "S1, S2, S3, S4"},
        ],
        "correct_option_ids": ["d"],
        "explanation": "The time markers fix the order: introduction (S1), 'At first' (S2), 'Over "
                       "time' (S3), 'By the 1700s' (S4). Option (a) places 'Over time' before 'At "
                       "first', (b) starts mid-story with an unexplained 'it', and (c) opens with "
                       "the conclusion.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_025",
        "skill": "Verbal Ability",
        "sub_domain": "ordering",
        "difficulty": "hard",
        "stem": "Arrange the sentences into the most coherent paragraph. S1: The scientist filled "
                "two identical jars with pond water. S2: She covered one jar with black cloth and "
                "left the other in sunlight. S3: A week later, the uncovered jar teemed with green "
                "algae. S4: The covered jar, by contrast, remained almost clear.",
        "options_json": [
            {"id": "a", "text": "S1, S2, S4, S3"},
            {"id": "b", "text": "S2, S1, S3, S4"},
            {"id": "c", "text": "S1, S3, S2, S4"},
            {"id": "d", "text": "S1, S2, S3, S4"},
        ],
        "correct_option_ids": ["d"],
        "explanation": "S1 must open (it introduces the two jars that S2's 'one jar … the other' "
                       "needs). S2 must precede the results, and S4's 'by contrast' requires S3's "
                       "algae result to contrast with — so only S1, S2, S3, S4 works. Option (a) "
                       "strands 'by contrast' with nothing to contrast, (b) uses 'one jar' before "
                       "any jars exist, and (c) reports results before the setup.",
        "negative_marking": 0.25,
    },
    # --- Idioms: idioms and contextual usage (026-030) ---
    {
        "id": "mcq_verbal_026",
        "skill": "Verbal Ability",
        "sub_domain": "idioms",
        "difficulty": "easy",
        "stem": "In the sentence 'We finally saw eye to eye on the budget,' the phrase 'saw eye to eye' means…",
        "options_json": [
            {"id": "a", "text": "watched carefully"},
            {"id": "b", "text": "argued"},
            {"id": "c", "text": "agreed"},
            {"id": "d", "text": "looked away"},
        ],
        "correct_option_ids": ["c"],
        "explanation": "'See eye to eye' means to agree (c), fitting a budget finally settled. "
                       "Watched carefully (a) and looked away (d) take 'eye' literally, and argued "
                       "(b) is the opposite of the phrase's meaning.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_027",
        "skill": "Verbal Ability",
        "sub_domain": "idioms",
        "difficulty": "easy",
        "stem": "In the sentence 'The new software cost an arm and a leg,' the phrase means it was…",
        "options_json": [
            {"id": "a", "text": "very expensive"},
            {"id": "b", "text": "painful to install"},
            {"id": "c", "text": "physically heavy"},
            {"id": "d", "text": "poorly designed"},
        ],
        "correct_option_ids": ["a"],
        "explanation": "'Cost an arm and a leg' means very expensive (a). Painful to install (b) and "
                       "physically heavy (c) read the body parts literally, and poorly designed (d) "
                       "confuses price with quality.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_028",
        "skill": "Verbal Ability",
        "sub_domain": "idioms",
        "difficulty": "medium",
        "stem": "In the sentence 'She decided to bite the bullet and apologize,' the phrase 'bite the bullet' means…",
        "options_json": [
            {"id": "a", "text": "to refuse an apology"},
            {"id": "b", "text": "to face something unpleasant with courage"},
            {"id": "c", "text": "to complain loudly"},
            {"id": "d", "text": "to delay a decision"},
        ],
        "correct_option_ids": ["b"],
        "explanation": "'Bite the bullet' means facing something unpleasant with courage (b) — here, "
                       "the apology. Refusing (a) and delaying (d) are the opposite of acting, and "
                       "complaining loudly (c) matches neither the phrase nor the context.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_029",
        "skill": "Verbal Ability",
        "sub_domain": "idioms",
        "difficulty": "medium",
        "stem": "In the sentence 'His excuse didn't hold water,' the phrase means the excuse…",
        "options_json": [
            {"id": "a", "text": "was too emotional"},
            {"id": "b", "text": "took too long"},
            {"id": "c", "text": "was not believable"},
            {"id": "d", "text": "was too short"},
        ],
        "correct_option_ids": ["c"],
        "explanation": "An excuse that 'doesn't hold water' is not believable (c). Too emotional "
                       "(a) invents a tone the sentence lacks, while took too long (b) and was too "
                       "short (d) mistake the idiom for a comment on length.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_verbal_030",
        "skill": "Verbal Ability",
        "sub_domain": "idioms",
        "difficulty": "hard",
        "stem": "In the sentence 'The committee's report was a white elephant,' the phrase 'a white elephant' means…",
        "options_json": [
            {"id": "a", "text": "a rare success"},
            {"id": "b", "text": "a costly possession of little use"},
            {"id": "c", "text": "a pleasant surprise"},
            {"id": "d", "text": "a controversial opinion"},
        ],
        "correct_option_ids": ["b"],
        "explanation": "A 'white elephant' is a costly possession of little use (b). A rare success "
                       "(a) and a pleasant surprise (c) wrongly read it as positive, and a "
                       "controversial opinion (d) confuses it with a dispute.",
        "negative_marking": 0.25,
    },
]


def seed_verbal_bank(session: Session) -> int:
    """Idempotently seed the 30 Verbal Ability MCQs. Returns rows inserted."""
    skill = session.scalars(
        select(SkillRow).where(SkillRow.canonical_name == VERBAL_SKILL)
    ).first()
    if skill is None:
        skill = SkillRow(canonical_name=VERBAL_SKILL, sub_domain="general")
        session.add(skill)
        session.flush()

    inserted = 0
    for fixture in PHASE21_VERBAL_BANK:
        if session.get(MCQQuestionRow, fixture["id"]) is None:
            session.add(MCQQuestionRow(
                id=fixture["id"],
                skill_id=skill.id,
                sub_domain=fixture["sub_domain"],
                difficulty=fixture["difficulty"],
                stem=fixture["stem"],
                options_json=fixture["options_json"],
                correct_option_ids=fixture["correct_option_ids"],
                explanation=fixture["explanation"],
                negative_marking=fixture["negative_marking"],
            ))
            inserted += 1
    session.commit()
    return inserted

