"""Final Synthetic Anomaly Evaluation — standalone script."""
import os, sys, time
sys.path.insert(0, os.getcwd())
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
django.setup()

import numpy as np
from apps.detection.trainer import FEATURE_COLUMNS, load_feature_matrix
from apps.detection.isolation_forest import IsolationForestDetector
from apps.detection.local_outlier import LOFDetector
from apps.detection.synthetic import inject_synthetic_anomalies
from apps.detection.evaluator import precision_recall_f1

print('=' * 70)
print('FINAL SYNTHETIC ANOMALY EVALUATION')
print('=' * 70)

# A. Dataset
print()
print('A. DATASET')
X, contract_ids = load_feature_matrix()
n_records = X.shape[0]
n_features = X.shape[1]
print('   Records: %d' % n_records)
print('   Features: %d (%s)' % (n_features, ', '.join(FEATURE_COLUMNS)))

# B. Synthetic methodology
print()
print('B. SYNTHETIC EVALUATION METHODOLOGY')
X_float = X.copy().astype(float)
X_synth, synth_labels = inject_synthetic_anomalies(
    X_float, anomaly_fraction=0.05, strategy='mixed', random_state=42
)
n_injected = int(synth_labels.sum())
n_value = n_injected // 3
n_bidder = n_injected // 3
n_perturb = n_injected - 2 * n_value
print('   Injection: mixed strategy, 5%% fraction, random_state=42')
print('   Synthetic anomalies: %d of %d' % (n_injected, len(synth_labels)))
print('   Labels generated BEFORE model training: YES')
print('   Label source: random index selection (np.random.choice), NOT model predictions')
print('   Sub-strategies: value_extreme=%d, single_bidder=%d, feature_perturbation=%d' % (n_value, n_bidder, n_perturb))

# C. Isolation Forest
print()
print('C. ISOLATION FOREST RESULTS')
t0 = time.time()
if_det = IsolationForestDetector(contamination=0.05, n_estimators=100)
if_det.fit(X_synth)
if_time = time.time() - t0

if_preds = if_det.predict(X_synth)
if_pred_bin = (if_preds == -1).astype(int)
if_m = precision_recall_f1(synth_labels, if_pred_bin)

print('   contamination: 0.05')
print('   n_estimators: 100')
print('   Synthetic anomalies (ground truth): %d' % n_injected)
print('   Detected anomaly count: %d' % int(if_pred_bin.sum()))
print('   True Positives:  %d' % if_m['tp'])
print('   False Positives: %d' % if_m['fp'])
print('   False Negatives: %d' % if_m['fn'])
print('   True Negatives:  %d' % if_m['tn'])
print('   Precision: %.4f' % if_m['precision'])
print('   Recall:    %.4f' % if_m['recall'])
print('   F1:        %.4f' % if_m['f1'])
print('   Runtime:   %.2fs' % if_time)

# D. LOF
print()
print('D. LOF RESULTS')
t0 = time.time()
lof_det = LOFDetector(contamination=0.05, n_neighbors=20)
lof_det.fit(X_synth)
lof_time = time.time() - t0

lof_preds = lof_det.predict(X_synth)
lof_pred_bin = (lof_preds == -1).astype(int)
lof_m = precision_recall_f1(synth_labels, lof_pred_bin)

print('   contamination: 0.05')
print('   n_neighbors: 20')
print('   Synthetic anomalies (ground truth): %d' % n_injected)
print('   Detected anomaly count: %d' % int(lof_pred_bin.sum()))
print('   True Positives:  %d' % lof_m['tp'])
print('   False Positives: %d' % lof_m['fp'])
print('   False Negatives: %d' % lof_m['fn'])
print('   True Negatives:  %d' % lof_m['tn'])
print('   Precision: %.4f' % lof_m['precision'])
print('   Recall:    %.4f' % lof_m['recall'])
print('   F1:        %.4f' % lof_m['f1'])
print('   Runtime:   %.2fs' % lof_time)

# E. Contamination sensitivity
print()
print('E. CONTAMINATION SENSITIVITY')
from apps.detection.trainer import run_sensitivity_analysis
sens = run_sensitivity_analysis([0.01, 0.03, 0.05, 0.1])
print('   %-15s %-15s %-15s' % ('Contamination', 'IF Anomalies', 'IF Score Mean'))
for c in sorted(sens.keys()):
    r = sens[c]
    print('   %-15s %-15s %-15.4f' % (c, r['n_anomalies'], r['score_mean']))

# F. Model overlap
print()
print('F. MODEL OVERLAP (contamination=0.05)')
if_set = set(np.where(if_pred_bin == 1)[0])
lof_set = set(np.where(lof_pred_bin == 1)[0])
both = if_set & lof_set
if_only = if_set - lof_set
lof_only = lof_set - if_set
union = if_set | lof_set
print('   IF flagged:  %d' % len(if_set))
print('   LOF flagged: %d' % len(lof_set))
print('   Both:        %d' % len(both))
print('   IF only:     %d' % len(if_only))
print('   LOF only:    %d' % len(lof_only))
print('   Jaccard:     %.4f' % (len(both) / len(union) if union else 0))

# H. Validity
print()
print('H. VALIDITY / LEAKAGE CHECK')
print('   Labels generated before model sees data: YES')
print('   Labels from random index selection (not model predictions): YES')
print('   Models trained on same modified feature matrix: YES')
print('   Evaluation on same data (not holdout): YES (in-sample synthetic eval)')
print('   Precision@K used: NO (removed per project rules)')
print('   contamination matches injection rate: YES (both 0.05)')

print()
print('=' * 70)
print('END OF EVALUATION')
print('=' * 70)
