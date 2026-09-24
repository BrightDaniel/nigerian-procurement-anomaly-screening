"""
Management command to generate SHAP explanations for anomaly flags.

Usage:
    python manage.py generate_explanations
    python manage.py generate_explanations --model isolation_forest
    python manage.py generate_explanations --model local_outlier_factor
"""
import logging

from django.core.management.base import BaseCommand

from apps.detection.models import AnomalyFlag
from apps.detection.trainer import FEATURE_COLUMNS, load_feature_matrix
from apps.detection.isolation_forest import IsolationForestDetector
from apps.explainability.models import Explanation
from apps.explainability.shap_explainer import SHAPExplainer
from apps.explainability.natural_language import generate_natural_language

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate SHAP explanations for anomaly flags'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            default='isolation_forest',
            choices=['isolation_forest', 'local_outlier_factor'],
            help='Model to generate explanations for',
        )
        parser.add_argument(
            '--top',
            type=int,
            default=0,
            help='Explain only top N anomalies by risk score (0 = all anomalies)',
        )

    def handle(self, *args, **options):
        model_name = options['model']
        top_n = options['top']

        self.stdout.write('Loading feature matrix...')
        X, contract_ids = load_feature_matrix()
        if X.empty:
            self.stdout.write(self.style.WARNING('No features available.'))
            return

        self.stdout.write(f'Training Isolation Forest for SHAP explainer...')
        detector = IsolationForestDetector(contamination=0.05)
        detector.fit(X)

        self.stdout.write('Initializing SHAP explainer...')
        explainer = SHAPExplainer(detector.model, feature_names=FEATURE_COLUMNS)
        if explainer.explainer is None:
            self.stdout.write(self.style.ERROR('SHAP explainer failed to initialize.'))
            return

        # Determine which contracts to explain
        flags = AnomalyFlag.objects.filter(
            model_used=model_name, is_anomaly=True
        )
        if top_n > 0:
            flags = flags.order_by('-risk_score')[:top_n]

        flag_list = list(flags)
        flag_contract_ids = [f.contract_id for f in flag_list]
        flag_indices = [contract_ids.index(cid) for cid in flag_contract_ids if cid in contract_ids]

        if not flag_indices:
            self.stdout.write(self.style.WARNING('No anomaly flags found to explain.'))
            return

        self.stdout.write(f'Generating SHAP explanations for {len(flag_indices)} anomalies...')
        top_X = X.iloc[flag_indices]
        result = explainer.explain(top_X, top_k=5)

        # Save explanations to Explanation model
        saved = 0
        for i, explanation in enumerate(result['explanations']):
            contract_id = flag_contract_ids[i]
            nl_text = generate_natural_language(explanation)

            Explanation.objects.update_or_create(
                contract_id=contract_id,
                model_used=model_name,
                defaults={
                    'shap_values': explanation['shap_values'],
                    'feature_importance': explanation['feature_importance'],
                    'force_plot_data': explanation.get('force_plot_data'),
                    'natural_language': nl_text,
                },
            )
            saved += 1

        self.stdout.write(self.style.SUCCESS(
            f'Generated and saved {saved} SHAP explanations for {model_name}.'
        ))

        # Print sample
        if result['explanations']:
            self.stdout.write('\n--- Sample explanation (highest-scored anomaly) ---')
            sample = result['explanations'][0]
            sample_nl = generate_natural_language(sample)
            self.stdout.write(f'Contract ID: {flag_contract_ids[0]}')
            self.stdout.write(f'Explanation: {sample_nl}')
            self.stdout.write('\nFeature contributions:')
            for fi in sample['feature_importance']:
                self.stdout.write(
                    f"  {fi['feature']}: value={fi['feature_value']:.4f}, "
                    f"shap={fi['shap_value']:.6f}, dir={fi['direction']}"
                )
