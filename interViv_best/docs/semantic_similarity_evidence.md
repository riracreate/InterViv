# Semantic Similarity Evidence — Change 3

**Date:** 2026-04-25
**Model:** sentence-transformers/all-MiniLM-L6-v2
**Test file:** tests/test_semantic.py
**Result:** 4/4 assertions passed

## Case results

| Case | Description | TF-IDF | Semantic | Delta |
|------|-------------|--------|----------|-------|
| A | Exact ideal (same text) | 1.0 | 1.0 | ≈ 0 (both ≈ 1.0) |
| B | Paraphrase — different words, same meaning | 0.1231 | 0.8473 | **+0.7242** in favour of semantic |
| C | Off-topic answer with borrowed vocabulary | 0.6979 | 0.4672 | -0.2307 |

## Key finding — Case B proves semantic adds signal

> **TF-IDF = 0.1231** on a correct paraphrase → would score as Poor
> **Semantic = 0.8473** on the same answer → correctly scores as Good
> **Delta: +0.7242**

Answers that express the correct concept using different terminology are no longer
penalised. The blended Layer 1 (60% semantic + 40% TF-IDF) gives them a fair score.

## Case C: why the semantic threshold is 0.55, not 0.40

MiniLM-L6 is trained for **topical** similarity, not factual correctness. An answer
from a completely different domain (food production) that borrows Docker vocabulary
scores Semantic ≈ 0.4672 because the model recognises the terms as being in the
same register. TF-IDF is more inflated at 0.6979, so semantic still correctly
discounts the answer relative to TF-IDF. The key property holds: semantic does not
blindly inflate scores for vocabulary-stuffed wrong answers.

## Layer 1 formula (after Change 3)

```
blended_cos = 0.60 × semantic_cosine + 0.40 × TF-IDF_cosine
  (falls back to pure TF-IDF when model unavailable or ideal is empty)

Layer1_score = (0.25 × blended_cos + 0.15 × keyword_coverage + 0.15 × concept_cov) / 0.55

NLP_score  = 0.55 × Layer1 + 0.25 × Layer2 + 0.20 × Layer3
final_score = 0.85 × NLP_score + 0.15 × KG_score
```

The formula weights and final_score formula are **unchanged**. Only what feeds
Layer 1's cosine term is different.
