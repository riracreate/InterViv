# interViv Colab Lab

This folder contains Google Colab-ready notebooks for testing the model and scoring stack.

Use these files if you want to upload the required files separately and let the notebook extract them:

- `interviv_model_lab_upload.ipynb`
- `interViv_best_required_files.zip`

Use this file if you want one notebook that runs by itself with everything embedded:

- `interviv_model_lab_standalone.ipynb`

Use this file only when the `interViv_best` folder is also available next to it:

- `interviv_model_lab.ipynb`

## Run On Colab

1. Go to <https://colab.research.google.com/>.
2. Click **File > Upload notebook**.
3. Upload `interviv_model_lab_upload.ipynb`.
4. In Colab's left Files panel, upload `interViv_best_required_files.zip`.
5. Click **Runtime > Run all**.
6. To test your own answer, edit the `CUSTOM` dictionary in section 7 and rerun that cell.

The upload notebook looks for `interViv_best_required_files.zip`, extracts it inside Colab, and then runs from the extracted model, data, and project files.

It loads:

- `modules/svm_model.joblib`
- `modules/nlp_scorer.py` and `modules/nlp_scorer_patch.py`
- `modules/knowledge_graph.py`
- `modules/ner_scorer.py`
- `modules/c4_feedback.py`
- `backend/scoring/pipeline.py`
- `data/ml_training_data.csv`
- `data/interview_dataset_v6.csv`

The notebook includes dataset charts, model feature importance, Good/Average/Poor comparisons, custom-answer scoring, an interactive answer tester, knowledge graph visuals, and a confusion matrix.

Regenerate the notebook after editing `build_notebook.py`:

```bash
python3 interviv_colab_lab/build_notebook.py
```
