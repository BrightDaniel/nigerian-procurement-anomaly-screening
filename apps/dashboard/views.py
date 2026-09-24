import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Q, F, Exists, OuterRef
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator

from apps.ingestion.models import Contract, ProcuringEntity, Vendor
from apps.features.models import Feature
from apps.detection.models import AnomalyFlag


def _default_priority(score):
    """Map anomaly score to priority label using percentile-based thresholds."""
    if score is None:
        return 'normal'
    s = float(score)
    if s >= 0.80:
        return 'high'
    elif s >= 0.60:
        return 'medium'
    return 'normal'


def _priority_label(priority):
    return {'high': 'High', 'medium': 'Medium', 'normal': 'Normal'}.get(priority, 'Normal')


@login_required
def index_view(request):
    """Dashboard — overview stats, distribution chart, top anomalies queue."""

    total_contracts = Contract.objects.count()
    total_anomalies = AnomalyFlag.objects.filter(is_anomaly=True).count()
    total_flagged = AnomalyFlag.objects.count()
    high_priority_count = AnomalyFlag.objects.filter(
        risk_score__gte=Decimal('0.80'), is_anomaly=True
    ).count()
    avg_score = AnomalyFlag.objects.aggregate(
        avg=Coalesce(Avg('risk_score'), Decimal('0'))
    )['avg']

    # Score distribution for histogram (buckets: 0-0.2, 0.2-0.4, ..., 0.8-1.0)
    buckets = ['0.0–0.2', '0.2–0.4', '0.4–0.6', '0.6–0.8', '0.8–1.0']
    bucket_ranges = [
        (Decimal('0.0'), Decimal('0.2')),
        (Decimal('0.2'), Decimal('0.4')),
        (Decimal('0.4'), Decimal('0.6')),
        (Decimal('0.6'), Decimal('0.8')),
        (Decimal('0.8'), Decimal('1.0')),
    ]
    distribution = []
    for low, high in bucket_ranges:
        count = AnomalyFlag.objects.filter(risk_score__gte=low, risk_score__lt=high).count()
        distribution.append(count)
    # Include exactly 1.0 in the last bucket
    distribution[-1] += AnomalyFlag.objects.filter(risk_score=Decimal('1.0')).count()

    # Top MDAs by flagged count
    top_mdas = (
        Contract.objects.filter(anomaly_flags__is_anomaly=True)
        .values(name=F('entity__name'))
        .annotate(count=Count('contract_id'))
        .order_by('-count')[:5]
    )
    mda_labels = [m['name'] or 'Unknown' for m in top_mdas]
    mda_counts = [m['count'] for m in top_mdas]

    # Top anomalies for priority queue
    top_anomalies = (
        AnomalyFlag.objects.filter(is_anomaly=True)
        .select_related('contract', 'contract__entity', 'contract__vendor')
        .order_by('-risk_score')[:10]
    )
    anomaly_queue = []
    for flag in top_anomalies:
        priority = _default_priority(flag.risk_score)
        anomaly_queue.append({
            'contract_id': flag.contract_id,
            'title': flag.contract.title[:60] + ('...' if len(flag.contract.title) > 60 else ''),
            'entity': flag.contract.entity.name if flag.contract.entity else '—',
            'vendor': flag.contract.vendor.name if flag.contract.vendor else '—',
            'amount': flag.contract.amount,
            'award_date': flag.contract.award_date,
            'score': flag.risk_score,
            'priority': priority,
            'priority_label': _priority_label(priority),
            'model_used': flag.model_used,
        })

    # Recent imports
    from apps.ingestion.models import RawRecord
    last_import = RawRecord.objects.order_by('-created_at').first()

    # Total entities and vendors
    total_entities = ProcuringEntity.objects.count()
    total_vendors = Vendor.objects.count()

    context = {
        'total_contracts': total_contracts,
        'total_anomalies': total_anomalies,
        'total_flagged': total_flagged,
        'high_priority_count': high_priority_count,
        'avg_score': round(float(avg_score), 4) if avg_score else 0,
        'total_entities': total_entities,
        'total_vendors': total_vendors,
        'has_data': total_contracts > 0,
        'has_anomalies': total_flagged > 0,
        'last_import': last_import,
        # Chart data
        'distribution_labels': json.dumps(buckets),
        'distribution_data': json.dumps(distribution),
        'mda_labels': json.dumps(mda_labels),
        'mda_data': json.dumps(mda_counts),
        # Priority queue
        'anomaly_queue': anomaly_queue,
    }
    return render(request, 'dashboard/index.html', context)


@login_required
def anomaly_detail_view(request, contract_id):
    """Anomaly Detail — investigation workspace for a single flagged record."""
    contract = get_object_or_404(
        Contract.objects.select_related('entity', 'vendor'),
        contract_id=contract_id
    )

    # Anomaly flag — get the highest-risk flag for this contract
    flag = AnomalyFlag.objects.filter(contract=contract).order_by('-risk_score').first()
    has_anomaly = flag is not None

    # Feature values
    try:
        feature = Feature.objects.get(contract=contract)
        has_features = True
    except Feature.DoesNotExist:
        feature = None
        has_features = False

    # Explanation — get explanation matching the flag's model
    from apps.explainability.models import Explanation
    if flag:
        explanation = Explanation.objects.filter(
            contract=contract, model_used=flag.model_used
        ).first()
    else:
        explanation = None
    has_explanation = explanation is not None

    # Compute priority
    priority = _default_priority(flag.risk_score) if flag else 'normal'
    priority_label = _priority_label(priority)

    # Compute rank (position among all anomalies)
    if flag:
        rank = AnomalyFlag.objects.filter(
            risk_score__gt=flag.risk_score, is_anomaly=True
        ).count() + 1
        total_anomalies = AnomalyFlag.objects.filter(is_anomaly=True).count()
    else:
        rank = None
        total_anomalies = 0

    # Feature contributions for display
    contributions = []
    if feature:
        feature_defs = [
            ('Contract Value', 'log_contract_value', float(feature.log_contract_value or 0), 'High' if feature.log_contract_value and float(feature.log_contract_value) > 15 else 'Moderate'),
            ('Price Deviation', 'price_deviation', float(feature.price_deviation or 0), 'High' if feature.price_deviation and abs(float(feature.price_deviation)) > 2 else ('Moderate' if feature.price_deviation and abs(float(feature.price_deviation)) > 1 else 'Lower')),
            ('Number of Bidders', 'num_bidders', float(contract.num_bidders or 0), 'High' if contract.num_bidders and contract.num_bidders == 1 else 'Lower'),
            ('Single Bidder', 'single_bidder_flag', 1.0 if feature.single_bidder_flag else 0.0, 'Moderate' if feature.single_bidder_flag else 'Lower'),
            ('Vendor Win Frequency', 'vendor_win_frequency', float(feature.vendor_win_frequency or 0), 'High' if feature.vendor_win_frequency and float(feature.vendor_win_frequency) > 0.05 else 'Lower'),
            ('Splitting Flag', 'splitting_flag', 1.0 if feature.splitting_flag else 0.0, 'Moderate' if feature.splitting_flag else 'Lower'),
        ]
        for name, field, value, level in feature_defs:
            contributions.append({
                'name': name,
                'value': value,
                'level': level,
                'bar_width': min(abs(value) * 100 / 20, 100) if value else 0,
                'direction': 'positive' if value > 0 else ('negative' if value < 0 else 'neutral'),
            })

    # Natural language explanation
    nl_explanation = explanation.natural_language if explanation else None
    if not nl_explanation and flag:
        # Generate a basic explanation
        parts = []
        if feature:
            if feature.single_bidder_flag:
                parts.append('only one bidder participated')
            if feature.price_deviation and abs(float(feature.price_deviation)) > 1:
                direction = 'above' if float(feature.price_deviation) > 0 else 'below'
                parts.append(f'its contract value is {abs(float(feature.price_deviation)):.1f} standard deviations {direction} the category average')
            if feature.vendor_win_frequency and float(feature.vendor_win_frequency) > 0.05:
                parts.append(f'this vendor has a relatively high win frequency ({float(feature.vendor_win_frequency)*100:.1f}%)')
            if feature.splitting_flag:
                parts.append(f'there are {feature.splitting_count} similar contracts from the same vendor and entity within 12 months')
        if parts:
            nl_explanation = f"This record was prioritised because {', '.join(parts[:3])}."
        else:
            nl_explanation = "This record was flagged based on the combined analysis of its procurement features. Detailed explanation is pending."

    # SHAP values for force plot
    shap_values = explanation.shap_values if explanation else None
    feature_importance = explanation.feature_importance if explanation else None
    force_plot_data = explanation.force_plot_data if explanation else None

    # If no force_plot_data, generate basic structure from contributions
    if not force_plot_data and contributions:
        force_plot_data = json.dumps({
            'features': [c['name'] for c in contributions],
            'values': [c['value'] for c in contributions],
            'directions': [1 if c['direction'] == 'positive' else (-1 if c['direction'] == 'negative' else 0) for c in contributions],
            'levels': [c['level'] for c in contributions],
        })

    context = {
        'contract': contract,
        'flag': flag,
        'feature': feature,
        'explanation': explanation,
        'has_anomaly': has_anomaly,
        'has_features': has_features,
        'has_explanation': has_explanation,
        'priority': priority,
        'priority_label': priority_label,
        'rank': rank,
        'total_anomalies': total_anomalies,
        'contributions': contributions,
        'nl_explanation': nl_explanation,
        'shap_values': shap_values,
        'force_plot_data': force_plot_data,
    }
    return render(request, 'dashboard/anomaly_detail.html', context)


# ─── Anomaly Queue ───

@login_required
def anomalies_view(request):
    """Anomaly Queue — all flagged records with filters, search, sort, pagination."""
    qs = (
        AnomalyFlag.objects.filter(is_anomaly=True)
        .select_related('contract', 'contract__entity', 'contract__vendor')
    )

    # Filters
    search = request.GET.get('search', '').strip()
    priority_filter = request.GET.get('priority', '')
    entity_id = request.GET.get('entity', '')
    vendor_id = request.GET.get('vendor', '')
    method = request.GET.get('method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if search:
        qs = qs.filter(
            Q(contract__title__icontains=search) |
            Q(contract_id__icontains=search) |
            Q(contract__entity__name__icontains=search) |
            Q(contract__vendor__name__icontains=search)
        )

    if priority_filter:
        if priority_filter == 'high':
            qs = qs.filter(risk_score__gte=Decimal('0.80'))
        elif priority_filter == 'medium':
            qs = qs.filter(risk_score__gte=Decimal('0.60'), risk_score__lt=Decimal('0.80'))
        elif priority_filter == 'normal':
            qs = qs.filter(risk_score__lt=Decimal('0.60'))

    if entity_id:
        qs = qs.filter(contract__entity_id=entity_id)
    if vendor_id:
        qs = qs.filter(contract__vendor_id=vendor_id)
    if method:
        qs = qs.filter(contract__method=method)
    if date_from:
        qs = qs.filter(contract__award_date__gte=date_from)
    if date_to:
        qs = qs.filter(contract__award_date__lte=date_to)

    # Sorting
    sort = request.GET.get('sort', '-risk_score')
    sort_map = {
        'score_asc': 'risk_score',
        'score_desc': '-risk_score',
        'date_asc': 'contract__award_date',
        'date_desc': '-contract__award_date',
        'amount_asc': 'contract__amount',
        'amount_desc': '-contract__amount',
        'id_asc': 'contract_id',
        'id_desc': '-contract_id',
    }
    order = sort_map.get(sort, '-risk_score')
    qs = qs.order_by(order)

    # Pagination
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Build row data
    anomaly_list = []
    for flag in page_obj:
        priority = _default_priority(flag.risk_score)
        anomaly_list.append({
            'contract_id': flag.contract_id,
            'title': flag.contract.title[:70] + ('...' if len(flag.contract.title) > 70 else ''),
            'entity': flag.contract.entity.name if flag.contract.entity else '—',
            'vendor': flag.contract.vendor.name if flag.contract.vendor else '—',
            'amount': flag.contract.amount,
            'award_date': flag.contract.award_date,
            'score': flag.risk_score,
            'priority': priority,
            'priority_label': _priority_label(priority),
            'method': flag.contract.method or '—',
        })

    # Filter choices
    all_entities = ProcuringEntity.objects.filter(contracts__anomaly_flags__is_anomaly=True).distinct().order_by('name')
    all_vendors = Vendor.objects.filter(contracts__anomaly_flags__is_anomaly=True).distinct().order_by('name')
    all_methods = (
        Contract.objects.filter(anomaly_flags__is_anomaly=True)
        .values_list('method', flat=True).distinct().order_by('method')
    )
    all_methods = [m for m in all_methods if m]

    total_count = paginator.count

    context = {
        'anomaly_list': anomaly_list,
        'page_obj': page_obj,
        'total_count': total_count,
        'all_entities': all_entities,
        'all_vendors': all_vendors,
        'all_methods': all_methods,
        'current_search': search,
        'current_priority': priority_filter,
        'current_entity': entity_id,
        'current_vendor': vendor_id,
        'current_method': method,
        'current_date_from': date_from,
        'current_date_to': date_to,
        'current_sort': sort,
    }
    return render(request, 'dashboard/anomalies.html', context)


# ─── Records ───

@login_required
def records_view(request):
    """Records — all imported contracts with filters, search, sort, pagination."""
    qs = Contract.objects.select_related('entity', 'vendor').all()

    # Annotate with anomaly flag status
    has_flag = Exists(AnomalyFlag.objects.filter(contract=OuterRef('pk'), is_anomaly=True))
    qs = qs.annotate(has_flag=has_flag)

    # Filters
    search = request.GET.get('search', '').strip()
    entity_id = request.GET.get('entity', '')
    vendor_id = request.GET.get('vendor', '')
    method = request.GET.get('method', '')
    category = request.GET.get('category', '')
    flagged = request.GET.get('flagged', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(contract_id__icontains=search) |
            Q(description__icontains=search) |
            Q(nocopo_id__icontains=search) |
            Q(entity__name__icontains=search) |
            Q(vendor__name__icontains=search)
        )

    if entity_id:
        qs = qs.filter(entity_id=entity_id)
    if vendor_id:
        qs = qs.filter(vendor_id=vendor_id)
    if method:
        qs = qs.filter(method=method)
    if category:
        qs = qs.filter(category=category)
    if flagged == 'yes':
        qs = qs.filter(has_flag=True)
    elif flagged == 'no':
        qs = qs.filter(has_flag=False)
    if date_from:
        qs = qs.filter(award_date__gte=date_from)
    if date_to:
        qs = qs.filter(award_date__lte=date_to)

    # Sorting
    sort = request.GET.get('sort', '-award_date')
    sort_map = {
        'date_asc': 'award_date',
        'date_desc': '-award_date',
        'amount_asc': 'amount',
        'amount_desc': '-amount',
        'id_asc': 'contract_id',
        'id_desc': '-contract_id',
        'title_asc': 'title',
        'title_desc': '-title',
    }
    order = sort_map.get(sort, '-award_date')
    qs = qs.order_by(order)

    # Pagination
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Build row data
    records_list = []
    for contract in page_obj:
        records_list.append({
            'contract_id': contract.contract_id,
            'title': contract.title[:70] + ('...' if len(contract.title) > 70 else ''),
            'entity': contract.entity.name if contract.entity else '—',
            'vendor': contract.vendor.name if contract.vendor else '—',
            'amount': contract.amount,
            'method': contract.method or '—',
            'category': contract.category or '—',
            'award_date': contract.award_date,
            'has_flag': contract.has_flag,
        })

    # Filter choices
    all_entities = ProcuringEntity.objects.filter(contracts__isnull=False).distinct().order_by('name')
    all_vendors = Vendor.objects.filter(contracts__isnull=False).distinct().order_by('name')
    all_methods = (
        Contract.objects.values_list('method', flat=True).distinct().order_by('method')
    )
    all_methods = [m for m in all_methods if m]
    all_categories = (
        Contract.objects.values_list('category', flat=True).distinct().order_by('category')
    )
    all_categories = [c for c in all_categories if c]

    total_count = paginator.count

    context = {
        'records_list': records_list,
        'page_obj': page_obj,
        'total_count': total_count,
        'all_entities': all_entities,
        'all_vendors': all_vendors,
        'all_methods': all_methods,
        'all_categories': all_categories,
        'current_search': search,
        'current_entity': entity_id,
        'current_vendor': vendor_id,
        'current_method': method,
        'current_category': category,
        'current_flagged': flagged,
        'current_date_from': date_from,
        'current_date_to': date_to,
        'current_sort': sort,
    }
    return render(request, 'dashboard/records.html', context)


@login_required
def record_detail_view(request, contract_id):
    """Record Detail — full contract view with anomaly assessment."""
    contract = get_object_or_404(
        Contract.objects.select_related('entity', 'vendor'),
        contract_id=contract_id
    )

    # Anomaly flag
    try:
        flag = AnomalyFlag.objects.get(contract=contract)
        has_anomaly = True
    except AnomalyFlag.DoesNotExist:
        flag = None
        has_anomaly = False

    # Feature values
    try:
        feature = Feature.objects.get(contract=contract)
        has_features = True
    except Feature.DoesNotExist:
        feature = None
        has_features = False

    # Explanation
    from apps.explainability.models import Explanation
    try:
        explanation = Explanation.objects.get(contract=contract)
        has_explanation = True
    except Explanation.DoesNotExist:
        explanation = None
        has_explanation = False

    # Compute priority
    priority = _default_priority(flag.risk_score) if flag else 'normal'
    priority_label = _priority_label(priority)

    # Compute rank
    if flag:
        rank = AnomalyFlag.objects.filter(
            risk_score__gt=flag.risk_score, is_anomaly=True
        ).count() + 1
        total_anomalies = AnomalyFlag.objects.filter(is_anomaly=True).count()
    else:
        rank = None
        total_anomalies = 0

    # Feature contributions
    contributions = []
    if feature:
        feature_defs = [
            ('Contract Value', 'log_contract_value', float(feature.log_contract_value or 0), 'High' if feature.log_contract_value and float(feature.log_contract_value) > 15 else 'Moderate'),
            ('Price Deviation', 'price_deviation', float(feature.price_deviation or 0), 'High' if feature.price_deviation and abs(float(feature.price_deviation)) > 2 else ('Moderate' if feature.price_deviation and abs(float(feature.price_deviation)) > 1 else 'Lower')),
            ('Number of Bidders', 'num_bidders', float(contract.num_bidders or 0), 'High' if contract.num_bidders and contract.num_bidders == 1 else 'Lower'),
            ('Single Bidder', 'single_bidder_flag', 1.0 if feature.single_bidder_flag else 0.0, 'Moderate' if feature.single_bidder_flag else 'Lower'),
            ('Vendor Win Frequency', 'vendor_win_frequency', float(feature.vendor_win_frequency or 0), 'High' if feature.vendor_win_frequency and float(feature.vendor_win_frequency) > 0.05 else 'Lower'),
            ('Splitting Flag', 'splitting_flag', 1.0 if feature.splitting_flag else 0.0, 'Moderate' if feature.splitting_flag else 'Lower'),
        ]
        for name, field, value, level in feature_defs:
            contributions.append({
                'name': name,
                'value': value,
                'level': level,
                'bar_width': min(abs(value) * 100 / 20, 100) if value else 0,
                'direction': 'positive' if value > 0 else ('negative' if value < 0 else 'neutral'),
            })

    # Natural language explanation
    nl_explanation = explanation.natural_language if explanation else None
    if not nl_explanation and flag:
        parts = []
        if feature:
            if feature.single_bidder_flag:
                parts.append('only one bidder participated')
            if feature.price_deviation and abs(float(feature.price_deviation)) > 1:
                direction = 'above' if float(feature.price_deviation) > 0 else 'below'
                parts.append(f'its contract value is {abs(float(feature.price_deviation)):.1f} standard deviations {direction} the category average')
            if feature.vendor_win_frequency and float(feature.vendor_win_frequency) > 0.05:
                parts.append(f'this vendor has a relatively high win frequency ({float(feature.vendor_win_frequency)*100:.1f}%)')
            if feature.splitting_flag:
                parts.append(f'there are {feature.splitting_count} similar contracts from the same vendor and entity within 12 months')
        if parts:
            nl_explanation = f"This record was prioritised because {', '.join(parts[:3])}."
        else:
            nl_explanation = "This record was flagged based on the combined analysis of its procurement features."

    context = {
        'contract': contract,
        'flag': flag,
        'feature': feature,
        'has_anomaly': has_anomaly,
        'has_features': has_features,
        'has_explanation': has_explanation,
        'priority': priority,
        'priority_label': priority_label,
        'rank': rank,
        'total_anomalies': total_anomalies,
        'contributions': contributions,
        'nl_explanation': nl_explanation,
    }
    return render(request, 'dashboard/record_detail.html', context)


# ─── Analytics views ───

@login_required
def analysis_runs_view(request):
    """Analysis Runs — list of detection model execution runs."""
    from apps.detection.models import AnalysisRun

    runs = AnalysisRun.objects.all()

    runs_data = []
    for run in runs:
        runs_data.append({
            'model_name': run.model_name.replace('_', ' ').title(),
            'model_key': run.model_name,
            'n_samples': run.n_samples,
            'n_anomalies': run.n_anomalies,
            'contamination': run.contamination,
            'score_mean': round(run.score_mean, 4) if run.score_mean else 0,
            'score_std': round(run.score_std, 4) if run.score_std else 0,
            'duration': f'{run.duration_seconds:.1f}s' if run.duration_seconds else '—',
            'status': run.status,
            'created_at': run.created_at,
        })

    context = {
        'runs': runs_data,
        'has_runs': len(runs_data) > 0,
    }
    return render(request, 'dashboard/analysis_runs.html', context)


@login_required
def model_performance_view(request):
    """Model Performance — evaluation metrics and model comparison."""
    import numpy as np
    from apps.detection.models import AnomalyFlag, AnalysisRun
    from apps.features.models import Feature
    from apps.detection.trainer import FEATURE_COLUMNS, load_feature_matrix
    from apps.detection.evaluator import precision_recall_f1
    from apps.detection.synthetic import inject_synthetic_anomalies
    from apps.detection.isolation_forest import IsolationForestDetector
    from apps.detection.local_outlier import LOFDetector

    # Get stats per model from AnomalyFlag
    models_stats = []
    for model_name in ['isolation_forest', 'local_outlier_factor']:
        flags = AnomalyFlag.objects.filter(model_used=model_name)
        total = flags.count()
        if total == 0:
            continue

        anomalies = flags.filter(is_anomaly=True).count()
        avg_score = flags.aggregate(avg=Avg('risk_score'))['avg'] or 0

        high = flags.filter(risk_score__gte=Decimal('0.80'), is_anomaly=True).count()
        medium = flags.filter(
            risk_score__gte=Decimal('0.60'), risk_score__lt=Decimal('0.80'), is_anomaly=True
        ).count()
        normal = anomalies - high - medium

        models_stats.append({
            'model_name': model_name.replace('_', ' ').title(),
            'model_key': model_name,
            'total_records': total,
            'anomaly_count': anomalies,
            'anomaly_rate': round(anomalies / total * 100, 2) if total > 0 else 0,
            'avg_score': round(float(avg_score), 4),
            'high_priority': high,
            'medium_priority': medium,
            'normal_priority': max(0, normal),
        })

    # Score distribution for comparison chart
    all_flags = AnomalyFlag.objects.all()
    score_ranges = ['0.0-0.2', '0.2-0.4', '0.4-0.6', '0.6-0.8', '0.8-1.0']
    range_bounds = [
        (0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)
    ]

    distribution = {}
    for model_name in ['isolation_forest', 'local_outlier_factor']:
        model_flags = all_flags.filter(model_used=model_name)
        dist = []
        for low, high in range_bounds:
            count = model_flags.filter(
                risk_score__gte=Decimal(str(low)),
                risk_score__lt=Decimal(str(high))
            ).count()
            dist.append(count)
        distribution[model_name] = dist

    # Run evaluation on real data
    eval_results = {}
    X, contract_ids = load_feature_matrix()
    if not X.empty:
        # Synthetic anomaly evaluation — inject directly into feature space
        X_float = X.copy().astype(float)
        X_synth_raw, synth_labels = inject_synthetic_anomalies(X_float, anomaly_fraction=0.05)

        synth_feature_cols = [c for c in FEATURE_COLUMNS if c in X_synth_raw.columns]
        X_synth = X_synth_raw[synth_feature_cols].fillna(0)

        # Train IF on synthetic data
        if_detector = IsolationForestDetector(contamination=0.05)
        if_detector.fit(X_synth)
        if_preds = if_detector.predict(X_synth)
        if_pred_binary = (if_preds == -1).astype(int)
        if_metrics = precision_recall_f1(synth_labels, if_pred_binary)
        eval_results['if_synth'] = if_metrics

        # Train LOF on synthetic data
        lof_detector = LOFDetector(contamination=0.05, n_neighbors=20)
        lof_detector.fit(X_synth)
        lof_preds = lof_detector.predict(X_synth)
        lof_pred_binary = (lof_preds == -1).astype(int)
        lof_metrics = precision_recall_f1(synth_labels, lof_pred_binary)
        eval_results['lof_synth'] = lof_metrics

    # Contamination sensitivity (compute live — AnalysisRun only has one contamination level)
    sensitivity_data = {}
    try:
        from apps.detection.trainer import run_sensitivity_analysis
        sensitivity_results = run_sensitivity_analysis([0.01, 0.03, 0.05, 0.1])
        for c, r in sensitivity_results.items():
            sensitivity_data[c] = {
                'n_anomalies': r['n_anomalies'],
                'n_samples': r.get('n_samples', 16637),
            }
    except Exception:
        pass

    context = {
        'models_stats': models_stats,
        'has_models': len(models_stats) > 0,
        'score_ranges': json.dumps(score_ranges),
        'distribution_data': json.dumps(distribution),
        'eval_results': eval_results,
        'has_eval': bool(eval_results),
        'sensitivity_data': sensitivity_data,
        'has_sensitivity': bool(sensitivity_data),
    }
    return render(request, 'dashboard/model_performance.html', context)
