# Mohler Short-Answer Grading Dataset (MohlerASAG)

- **Source Repository**: https://huggingface.co/datasets/nkazi/MohlerASAG
- **Pinned Revision / Commit SHA**: `dac06732b42d01a5169f543f6d272f1476cced3e`
- **License**: `CC-BY-4.0` (verified in Hugging Face dataset metadata / `HF_README.md`)
- **Original Citation**:
  Michael Mohler, Razvan Bunescu, and Rada Mihalcea. *Learning to Grade Short Answer Questions using Semantic Similarity Measures and Dependency Graph Alignments*. ACL-HLT 2011.
- **Original UNT Dataset Details**:
  87 Computer Science / Data Structures assignment and exam questions (`81` open-ended in `raw-oe`, `6` close-ended in `raw-ce`) with `2,442` total student answers (`2,273` open-ended, `169` close-ended), each graded by two human annotators with averaged target `score_avg` normalized to `0.0–5.0`.

## Files and Checksums (SHA-256)

### Downloaded Raw Files
| File | URL | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `HF_README.md` | `https://huggingface.co/datasets/nkazi/MohlerASAG/resolve/dac06732b42d01a5169f543f6d272f1476cced3e/README.md` | 11271 | `0a1a38237d2c08fcdee62a18cdd349a7779573907e3bac39188f6b60911b4aa6` |
| `raw/raw-oe-00001.parquet` | `https://huggingface.co/datasets/nkazi/MohlerASAG/resolve/dac06732b42d01a5169f543f6d272f1476cced3e/data/raw-oe-00001.parquet` | 150308 | `6b120a31aac6eb69e5922b954f8dfc27846177394b8d8e6a7590b5741b19cc7c` |
| `raw/raw-ce-00001.parquet` | `https://huggingface.co/datasets/nkazi/MohlerASAG/resolve/dac06732b42d01a5169f543f6d272f1476cced3e/data/raw-ce-00001.parquet` | 11599 | `7e7938f9c8b23d295630479962735601b2d805cc71dd9280af62cbfda3683ade` |

### Exported UTF-8 CSV Splits
| File | Rows | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| `mohler_raw_open_ended.csv` | 2273 | 655741 | `19024e8d5daed13f0554ca85bb6a2b9caeb47a19206f3308ace3cf1e71b6ae92` |
| `mohler_raw_close_ended.csv` | 169 | 37095 | `f43832674f6fffcb6f74ea8c76afdfaeabc6eb4a883f323006d0756bc928b8a9` |
| `mohler_raw_all.csv` | 2442 | 692743 | `53f506ea1c0e13390f194d999d02a6d0aac3b3242d8271e92bde4fb0df5e8d10` |
