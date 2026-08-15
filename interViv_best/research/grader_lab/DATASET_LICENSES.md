# Dataset license review

Reviewed: 2026-08-15

This review is a repository compliance note, not legal advice.

## Pre-flight decision

| Dataset | License | Commercial use in this codebase | Decision | Primary source |
| --- | --- | --- | --- | --- |
| SciEntsBank (SemEval-2013 Task 7) | Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0) | Permitted, provided attribution and ShareAlike terms are honored for the dataset and adaptations | Cleared for the research harness | [Pinned task organizer dataset repository](https://github.com/myrosia/semeval-2013-task7/tree/5157c69f914e8c581045c03e98f96398d40a91b8) and its [license text](https://github.com/myrosia/semeval-2013-task7/blob/5157c69f914e8c581045c03e98f96398d40a91b8/LICENSE) |
| BEETLE (SemEval-2013 Task 7) | Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0) | Permitted, provided attribution and ShareAlike terms are honored for the dataset and adaptations | Cleared for the research harness | [Pinned task organizer dataset repository](https://github.com/myrosia/semeval-2013-task7/tree/5157c69f914e8c581045c03e98f96398d40a91b8) and its [license text](https://github.com/myrosia/semeval-2013-task7/blob/5157c69f914e8c581045c03e98f96398d40a91b8/LICENSE) |
| RiceChem | No files or grant of access supplied | Not evaluated | `pending_access`; do not add or run data until its terms are reviewed | N/A |

## Basis for the decision

The SemEval-2013 Task 7 repository is published by task organizer Myroslava Dzikovska and identifies the packaged dataset as CC BY-SA. Its `LICENSE` file contains the CC BY-SA 3.0 Unported legal code. The package contains both corpus subsets described in the [official task paper](https://aclanthology.org/S13-2045/): BEETLE and SciEntsBank. The pinned source revision used by this lab is `5157c69f914e8c581045c03e98f96398d40a91b8`.

CC BY-SA 3.0 has no NonCommercial restriction. Its license grant permits reproduction, distribution, and adaptations, including commercial use, subject to its conditions. The authoritative [Creative Commons license page](https://creativecommons.org/licenses/by-sa/3.0/) summarizes the required attribution and ShareAlike obligations.

SemEval itself does not impose one universal dataset license: its [official FAQ](https://semeval.github.io/faq.html) says task datasets are distributed by their task organizers. The Task 7 organizer repository is therefore the controlling source used for this review. Third-party mirrors that label the package only as generic `cc`, or describe intended research uses without a precise grant, were not used as the license authority.

## Repository handling requirements

- Keep SemEval-derived JSONL data in a clearly separated data directory with CC BY-SA attribution and license text.
- Preserve the source authors, task citation, source URL, pinned revision, and a notice that XML-to-JSONL normalization modified the format.
- Distribute adaptations of the dataset under CC BY-SA 3.0 or a compatible license. This requirement applies to the dataset adaptation; the surrounding code remains a separately identifiable collection component.
- Do not treat benchmark availability as permission to use learner data for product training or production decisions. This module is evaluation-only.
- Keep RiceChem at `pending_access` until both files and explicit terms are available.
