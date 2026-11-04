import pandas as pd
import pytest

from retrain_ml_model import split_by_question


def test_question_variants_cannot_leak_between_holdout_or_cv_folds():
    rows = []
    for i in range(30):
        for label, variant in zip(("Good", "Average", "Poor"), (f"Question {i}", f"QUESTION {i}", f"  Question   {i}  ")):
            rows.append({"question": variant, "label": label})
    df = pd.DataFrame(rows)
    train, test, folds, groups = split_by_question(df)
    assert len(set(groups)) == 30
    assert set(train).isdisjoint(test)
    assert len(train) + len(test) == len(df)
    assert set(groups[train]).isdisjoint(groups[test])
    validation_rows = []
    for fit, validation in folds:
        assert set(groups[train][fit]).isdisjoint(groups[train][validation])
        validation_rows.extend(validation)
    assert sorted(validation_rows) == list(range(len(train)))


def test_missing_question_identity_cannot_fall_back_to_row_split():
    with pytest.raises(ValueError, match="question column"):
        split_by_question(pd.DataFrame({"label": ["Good"]}))
    with pytest.raises(ValueError, match="nonempty"):
        split_by_question(pd.DataFrame({"label": ["Good"], "question": [None]}))
