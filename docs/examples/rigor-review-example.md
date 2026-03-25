# Example: Rigor Review
>[!NOTE]
> **Agent:** `@sci-reviewer`  
> **Domain:** Machine Learning Applications with Electrophysiological data  
> **What was reviewed:** Jupyter Notebook with 12 cells [mms_hierarch_grid.ipynb](https://github.com/smestern/pypatchOTDA/blob/main/notebooks/mms_hierarch_grid.ipynb)
>
>---
>
>## Task
>
>In this task, I have a script that I want to review for rigour. In this script, I am attempting >to train a hierarchical classifier on data extracted from intracellular neuron recordings [(long story, see more here)](https://alleninstitute.org/events/mapmyspikes/).
>
>This dataset is tabular, and also features hierarchical labels that reflect neuron cell types, sub cell types, and *sub* sub cell types. Moreover, its very imbalanced. As such, I have quite a complicated research code here, where I employ things like label balancing, hyperparameter scanners, and cross validation. 
>
>Here I ask the rigour reviewer to help me out. I am worried I accidentally have some data leakage, as I am getting good performance in testing, but poor performance on completely new datasets.
>
>## Key Takeaway
>
>The reviewer identified a subtle **preprocessing-induced data leakage** — `KNNImputer` and `StandardScaler` were fit on the full training set *before* the cross-validation loop, meaning validation-fold statistics bled into the imputation and scaling steps. This is a domain-aware catch: a generic LLM would likely praise the code for "using cross-validation correctly," whereas the reviewer traced the data flow across notebook cells to show that the CV error estimates were optimistically biased despite the split itself being valid. It also caught that `k_neighbors` differed between CV and final training a configuration mismatch that only matters in the context of SMOTE resampling with imbalanced hierarchical labels, not something a surface-level review would flag.
>
>---

# *Example: Transcript*


<div style="text-align: right">  <b>User:</b>

Review the following code for rigour. I'm particularly concerned about data leakage.</div>


**Model:**  
I've read the full notebook. Here is my review.

## Code Review: mms_hierarch_grid.ipynb

### Summary
**Overall assessment: REVISE**  
Key concerns: Preprocessing-induced data leakage inside cross-validation; train/eval mismatch in SMOTEENN configuration; non-reproducible optimization.

### Issues

| # | Severity | Location | Issue | Suggestion |
|---|----------|----------|-------|------------|
| 1 | **CRITICAL** | Impute/scale cell (cell 4) + error_func (cell 5) | **KNNImputer + StandardScaler data leakage into CV validation folds.** `impute_and_scale.fit_transform(Xs_train)` is called *once* on the full training set *before* the 5-fold CV in `error_func`. Every CV validation fold's values contributed to the KNN neighbor graph (imputation) and to the mean/std (scaling). The validation fold is therefore not truly unseen — CV error estimates will be optimistically biased. This is the classic "preprocessing before splitting" leak. | Move imputation and scaling *inside* each CV fold: fit on `Xs_cv_train`, transform both `Xs_cv_train` and `Xs_cv_val`. Also move the fit inside the final-model training cell for consistency. The test set transform should use a pipeline fit only on the (possibly resampled) training data. |
| 2 | **CRITICAL** | Final training cell (cell 8) | **SMOTEENN `k_neighbors` mismatch between CV and final training.** CV calls `resample_hierarchical(...)` with the default `k_neighbors=3`, but final training uses `k_neighbors=1`. The resampled distribution the final model sees differs from what was evaluated during hyperparameter selection — the selected hyperparameters may not be optimal for the `k_neighbors=1` regime, and vice versa. | Use the same `k_neighbors` value in both. If `k_neighbors=1` is needed for small classes, use it consistently inside `error_func` as well (or make it a tuned parameter). |
| 3 | **WARNING** | Optimizer cell (cell 5) | **Non-reproducible optimization.** `ng.optimizers.Portfolio` has no `random_state` or seed set. Combined with `ThreadPoolExecutor` and `batch_mode=False`, the optimization trajectory is non-deterministic — results will differ across runs even with identical data. | Set `np.random.seed(...)` before optimizer creation (nevergrad respects numpy's global RNG in some backends) and use `batch_mode=True` for deterministic batch evaluation. Document that exact reproducibility requires single-threaded execution. |
| 4 | **WARNING** | error_func (cell 5) | **Bare `except Exception` silently swallows SMOTEENN failures.** If resampling fails (e.g., a class has fewer samples than `k_neighbors`), the fallback to un-resampled data happens silently. Some CV folds may be resampled and others not, making the CV estimate inconsistent. | At minimum, log the exception. Better: catch only the specific `ValueError` from SMOTE and record which folds fell back. Consider whether falling back is scientifically appropriate or whether the fold should be excluded. |
| 5 | **WARNING** | Confusion matrix cell (cell 12) | **`label_encoder` variable shadowed.** `label_encoder` is initially a `LabelEncoder` (cell 4), then reassigned to `MMS_DATA['VISp_Viewer'].keys()` (cell 11), then to a different `LabelEncoder` from `MMS_DATA` per loop iteration (cells 12–13). If cells are re-executed out of order, the wrong encoder will be used, silently producing incorrect confusion matrices. | Use distinct variable names (e.g., `smote_label_encoder` vs `display_label_encoder`) to avoid shadowing. |
| 6 | **WARNING** | Label encoding/decoding (cell 4) | **`label_encoder` fit on `Ys_train` only — CV validation folds may contain class combinations unseen during fit.** `LabelEncoder` is fit on `Ys_train_combined` before CV. If a particular 3-level label combination appears only in a CV validation fold (after the KFold split), `le.transform()` in `resample_hierarchical` will raise an error on the training fold, triggering the silent fallback. Unlikely but not impossible with rare classes. | Fit the label encoder on all known class combinations from the full dataset (labels only — no feature leakage), or handle unseen combinations explicitly. |
| 7 | **WARNING** | Entire notebook | **No library versions documented.** `hiclass`, `imblearn`, `nevergrad`, `scikit-learn`, `xgboost` versions are not recorded. Behavior of SMOTEENN, hiclass wrappers, and nevergrad Portfolio can differ across versions. | Add a cell that prints or records `pkg.__version__` for all critical dependencies, or pin versions in a requirements.txt. |
| 8 | **STYLE** | Confusion matrix save (cell 13) | **Hardcoded absolute path** `/home/smestern/pypatchOTDA/tests/confusion_matrix_{level}.png`. | Use a relative path or a configurable output directory. |
| 9 | **STYLE** | Imports cell (cell 1) | **`class_model = "Random Forest"` is defined but never used.** `streamlit`, `altair`, `zipfile`, `umap`, `tree_select`, and several sklearn imports are also unused. | Remove dead imports and variables to reduce confusion about what the notebook actually depends on. |
| 10 | **INFO** | Results cell (cell 9) | **Training accuracy is computed on original (non-resampled) `Xs_train`.** This is arguably correct for reporting natural-distribution performance, but it should be noted explicitly since the model was trained on resampled data. The train/test comparison may be misleading without this context. | Add a comment or markdown cell clarifying that train accuracy is on the original distribution. |

### Positive Aspects
- SMOTEENN is correctly applied *inside* each CV fold (not before the split) — the intent is right, only the preprocessing step leaks.
- Test set is properly held out from hyperparameter tuning — no test-set leakage.
- `random_state=42` is set for `train_test_split`, `KFold`, and `SMOTE`.
- Thread safety is handled well: fresh SMOTEENN instances per call, non-destructive dict access, read-only `label_encoder`.
- Balanced accuracy is the right metric for imbalanced hierarchical classification.
- Weighted hierarchy loss (0.5/0.3/0.2) is a sensible design choice for prioritizing coarse-level accuracy.

### Recommendations (priority order)

1. **Move imputation + scaling inside the CV loop.** This is the most impactful fix. Define a function that takes raw (unscaled) fold data, fits the pipeline on the train fold, and transforms both folds. Apply the same pipeline to the final train/test split independently.

2. **Unify `k_neighbors`** between CV and final training. The comment in cell 8 says "matches what each CV fold did" — but it doesn't.

3. **Add determinism controls** for nevergrad (seed, batch mode) or document that results are approximate.

4. **Log SMOTEENN fallback events** rather than silently catching them.

5. **Use distinct variable names** for the multiple `label_encoder` objects to prevent out-of-order execution bugs.

---

