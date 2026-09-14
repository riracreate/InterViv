# Gemma hint-coach artifact inventory (Phase 1B Task F)

Read-only audit. Prepared during Phase 1B on 14 September 2026.
**Nothing in this document was imported into the Phase 1B worktree or wired into scoring.**

## Three distinct things

| # | What | Where / status in this repo |
| --- | --- | --- |
| 1 | Stock coding coach (`gemma2:2b` via Ollama) | Working app: `backend/coding_coach.py` (`DEFAULT_MODEL = "gemma2:2b"`). Present on unify-shell / Phase 0 / 1A / 1B. Preserved. |
| 2 | User fine-tuned Gemma 2 hint-coach (QLoRA SFT) | Untracked Tree 2 + repo-root training package + weight zips (below). **Not integrated into Phase 1B.** |
| 3 | Gemma 4 (possible later comparison base) | Not present. No weights, notebooks, or app wiring found. |

## Verified artifact paths (Tree 2 / repo root)

All of the following are **untracked** on `ticket-f/integrate-demo` @ `13ac259` (dirty checkout). Inspected read-only; not staged, copied, or deleted.

| Path | Role |
| --- | --- |
| `hint_coach_training/` | Self-contained Kaggle training package (notebook, `training.py`, `coachlib.py`, data, tests, Ollama helpers) |
| `hint_coach_training/notebooks/gemma2_hint_coach_qlora_dpo.ipynb` | Primary Kaggle entry |
| `hint_coach_training/data/hint_coach_sft.jsonl` | 69 SFT rows (33 original + 36 synthetic) |
| `hint_coach_training/data/hint_coach_dpo.jsonl` | 36 DPO pairs (DPO off in the train-v2 run) |
| `hint_coach_training/data/heldout_eval.jsonl` | 18 held-out prompts (problem-group disjoint from this fine-tune corpus) |
| `hint_coach_training/data/provenance.json` | States synthetic additions; no independent human ratings |
| `hint_coach_training/docs/validation_report.json` | CPU validation only; `gpu_training_executed: false` in that report (local editing env) — the weight zip separately proves a GPU train ran |
| `archive/weights/hint-coach-train-v2_artifacts.zip` | Train-mode artifact (~161 MB) with `sft_adapter/` |
| `archive/weights/hint-coach-smoke-v2_artifacts.zip` | Smoke-mode artifact (~160 MB); pipeline check only |
| `interViv_best/modules/hint_coach.py` | Uncommitted Tree 2 serving module (Ollama `hint-coach` model name, structural screens). **Not imported.** |
| `interViv_best/docs/hint_coach.md`, `interViv_best/tests/test_hint_coach.py` | Present as untracked Tree 2 companions (not opened into Phase 1B) |

Phase 1B worktree confirms absence: `.worktrees/cursor-ai-design-phase1b/interViv_best/modules/hint_coach.py` does not exist.

## Train-v2 facts established from zip manifests (not from filenames alone)

From `hint-coach-train-v2/run_manifest.json`, `adapter_config.json`, `final_selection.json`, `sft_metrics.json` inside `archive/weights/hint-coach-train-v2_artifacts.zip`:

| Field | Value |
| --- | --- |
| Base model | `unsloth/gemma-2-2b-it` (public mirror of Gemma 2 2B IT) |
| Resolved revision | `457f2e15bf550c227ce6ad86e2ec108d3e42c106` |
| Adapter | PEFT LoRA / QLoRA-style: `r=32`, `alpha=64`, dropout `0.1`, targets q/k/v/o/gate/up/down proj |
| Export | `sft_adapter/adapter_model.safetensors` + tokenizer files (adapter, not a claimed full merge) |
| Run mode | `train` / `hint-coach-train-v2`; `run_dpo: false` |
| Selected stage | SFT (`final_selection.json`); not an automatic claim that DPO is better |
| Train loss / eval loss | `train_loss ≈ 1.53`, `eval_loss ≈ 2.81` after 5 epochs (loss ≠ usefulness) |
| GPU recorded | Tesla T4, bf16 |
| Package pin examples | transformers 4.52.4, trl 0.19.1, peft 0.15.2, torch 2.10.0+cu128 |

Smoke zip is the short pipeline check (`smoke_only` path); do not treat it as the production candidate.

## Task coverage

- **Coding interview hints** (progressive levels 1–3; Socratic / pattern / bug-local). Prompt text in Tree 2 `hint_coach.py` matches training `SYSTEM_PROMPT`.
- **SQL coaching:** no SQL-ish rows detected in `hint_coach_sft.jsonl` (0/69). Treat SQL coverage as **absent / unknown for this fine-tune**.
- **Scoring / mastery / Elo:** explicitly out of scope for the serving module docstring (“No scoring”).

## What the app actually loads today

- Day-to-day / Phase 1B coding coach: stock Ollama **`gemma2:2b`** via `backend/coding_coach.py`.
- Fine-tuned `hint-coach` adapter is **not** loaded by the Phase 1B tree. Tree 2’s uncommitted `modules/hint_coach.py` would talk to Ollama model name `hint-coach` if enabled there; that wiring was **not** imported.

## Missing / unknown (honest gaps)

- Independent human ratings of hint quality (provenance says none supplied).
- Measured improvement vs stock Gemma 2 on held-out coaching tasks (format flags ≠ correctness; README states no measured improvement claim).
- Whether a GGUF/Ollama model named `hint-coach` is installed on any local machine used with Tree 2 (`gguf_conversion_executed` / `ollama_inference_executed` false in the package validation report).
- Full Trainer optimizer checkpoints beyond the exported adapter (may exist only in Kaggle run directories).
- Any Gemma 4 artifact.

## Proposed later comparison (not executed in Phase 1B)

Same unseen coaching tasks for:

1. Stock `gemma2:2b` (current app coach)
2. Fine-tuned Gemma 2 hint-coach adapter (train-v2)
3. Untuned Gemma 4 (when available)

Score at least: correctness, false praise, spoilers (full solution / equivalent prose), format reliability, latency, peak memory. Keep scoring pipelines untouched. Do not promote a coach from training loss alone.

## Phase 1B non-actions (confirmed)

- No retrain, no weight download into the worktree, no import of `modules/hint_coach.py` / SQL wiring / `hint_coach_training/` into the app tree.
- No model binaries committed.
- No replacement of the stock Gemma coding coach.
