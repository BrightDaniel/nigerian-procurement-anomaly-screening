"""
Management command to run anomaly detection pipeline.

Usage:
    python manage.py run_detection [--contamination 0.05] [--model isolation_forest]
    python manage.py run_detection --sensitivity
"""
import json
import logging
import time

from django.core.management.base import BaseCommand, CommandError

from apps.detection.trainer import (
    train_isolation_forest,
    train_lof,
    run_sensitivity_analysis,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run anomaly detection pipeline'

    def add_arguments(self, parser):
        parser.add_argument(
            '--contamination',
            type=float,
            default=0.05,
            help='Expected anomaly proportion (default: 0.05)',
        )
        parser.add_argument(
            '--model',
            type=str,
            default='isolation_forest',
            choices=['isolation_forest', 'lof'],
            help='Detection model to use (default: isolation_forest)',
        )
        parser.add_argument(
            '--sensitivity',
            action='store_true',
            help='Run contamination sensitivity analysis',
        )
        parser.add_argument(
            '--no-save',
            action='store_true',
            help='Do not save results to database',
        )

    def handle(self, *args, **options):
        contamination = options['contamination']
        model = options['model']
        sensitivity = options['sensitivity']
        save = not options['no_save']

        self.stdout.write(f'Running {model} with contamination={contamination}')

        try:
            if sensitivity:
                self.stdout.write('Running sensitivity analysis...')
                results = run_sensitivity_analysis()
                self.stdout.write(self.style.SUCCESS('Sensitivity analysis complete'))
                for c, r in results.items():
                    self.stdout.write(
                        f'  contamination={c}: {r["n_anomalies"]} anomalies, '
                        f'mean_score={r["score_mean"]:.4f}'
                    )
            else:
                start = time.time()
                if model == 'isolation_forest':
                    results = train_isolation_forest(contamination=contamination, save=save)
                elif model == 'lof':
                    results = train_lof(contamination=contamination, save=save)
                else:
                    raise CommandError(f'Unknown model: {model}')
                duration = time.time() - start

                self.stdout.write(self.style.SUCCESS(
                    f'Detection complete: {results.get("n_anomalies", 0)} anomalies '
                    f'out of {results.get("n_samples", 0)} samples'
                ))

                if save and 'error' not in results:
                    from apps.detection.models import AnalysisRun
                    AnalysisRun.objects.create(
                        model_name=model,
                        contamination=contamination,
                        n_samples=results.get('n_samples', 0),
                        n_features=results.get('n_features', 0),
                        n_anomalies=results.get('n_anomalies', 0),
                        score_mean=results.get('score_mean'),
                        score_std=results.get('score_std'),
                        score_min=results.get('score_min'),
                        score_max=results.get('score_max'),
                        duration_seconds=round(duration, 2),
                        params=results.get('params'),
                    )
                    self.stdout.write(f'Run saved to database.')

                    # Auto-generate SHAP explanations
                    model_used = 'isolation_forest' if model == 'isolation_forest' else 'local_outlier_factor'
                    self.stdout.write(f'Generating SHAP explanations for {model_used}...')
                    try:
                        from apps.detection.trainer import load_feature_matrix
                        from apps.detection.isolation_forest import IsolationForestDetector
                        from apps.explainability.models import Explanation
                        from apps.explainability.shap_explainer import SHAPExplainer
                        from apps.explainability.natural_language import generate_natural_language
                        from apps.detection.models import AnomalyFlag

                        X, cids = load_feature_matrix()
                        if not X.empty:
                            if_det = IsolationForestDetector(contamination=contamination)
                            if_det.fit(X)
                            shap_exp = SHAPExplainer(if_det.model)
                            if shap_exp.explainer is not None:
                                flags = AnomalyFlag.objects.filter(
                                    model_used=model_used, is_anomaly=True
                                )
                                flag_cids = [f.contract_id for f in flags]
                                indices = [cids.index(cid) for cid in flag_cids if cid in cids]
                                if indices:
                                    top_X = X.iloc[indices]
                                    result = shap_exp.explain(top_X, top_k=5)
                                    saved_exp = 0
                                    for j, expl in enumerate(result['explanations']):
                                        Explanation.objects.update_or_create(
                                            contract_id=flag_cids[j],
                                            model_used=model_used,
                                            defaults={
                                                'shap_values': expl['shap_values'],
                                                'feature_importance': expl['feature_importance'],
                                                'force_plot_data': expl.get('force_plot_data'),
                                                'natural_language': generate_natural_language(expl),
                                            },
                                        )
                                        saved_exp += 1
                                    self.stdout.write(f'Saved {saved_exp} SHAP explanations.')
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'SHAP explanation generation failed: {e}'))

        except Exception as e:
            raise CommandError(f'Detection failed: {e}')
