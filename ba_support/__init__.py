"""ba_support: British Airways support-agent pipeline (Hiver SDE Intern Take-Home).

Modules
-------
- paths       : repository anchors, dataset locations, seed policy
- taxonomy    : label enums (single source of truth = analysis/scripts/_taxonomy.py)
- normalize   : text normalisation, redaction, near-duplicate helpers
- weak        : rule-based weak (distant) supervision over the BA corpus
- corpus      : leakage-controlled retrieval/training corpus builder
- leakage     : golden-set isolation manifests and checks
- intent      : majority / TF-IDF+LR / hybrid with-rule classifiers
- retrieval   : TF-IDF evidence retrieval with filters + quality metrics
- escalation  : deterministic operational escalation policy
- generate    : evidence-grounded draft reply generator
- judge       : LLM-as-judge (offline fallback + optional OpenAI)
- evaluate    : metric aggregation, results serialisation
- pipeline    : end-to-end single-example predictor

Honesty rules enforced here: the golden set (200 examples) is assistant-drafted
and is NEVER used for training, model fitting, or evidence retrieval. All
supervised training uses weakly-labelled, leakage-excluded BA corpus rows.
"""

__version__ = "1.0.0"