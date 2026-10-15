from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Max, Exists, OuterRef, Prefetch
from django.core.paginator import Paginator

from apps.ingestion.models import Contract, ProcuringEntity
from apps.detection.models import AnomalyFlag
from apps.features.models import Feature
from apps.explainability.models import Explanation
from apps.core.priority import (
    HIGH_MIN_SCORE,
    MEDIUM_MIN_SCORE,
    priority_for_score,
    priority_label,
)
from .models import InvestigationReport

_default_priority = priority_for_score
_priority_label = priority_label


@login_required
def report_list_view(request):
    """Investigation Reports — flagged contracts with investigation status."""
    qs = (
        Contract.objects.filter(
            Exists(
                AnomalyFlag.objects.filter(contract=OuterRef('pk'), is_anomaly=True)
            )
        )
        .select_related('entity', 'vendor')
        .annotate(
            best_score=Max(
                'anomaly_flags__risk_score',
                filter=Q(anomaly_flags__is_anomaly=True),
            )
        )
        .order_by('-best_score', '-contract_id')
    )

    # Filters
    search = request.GET.get('search', '').strip()
    priority_filter = request.GET.get('priority', '')
    entity_id = request.GET.get('entity', '')

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(contract_id__icontains=search) |
            Q(entity__name__icontains=search) |
            Q(vendor__name__icontains=search)
        )

    if entity_id:
        qs = qs.filter(entity_id=entity_id)

    if priority_filter == 'high':
        qs = qs.filter(best_score__gte=HIGH_MIN_SCORE)
    elif priority_filter == 'medium':
        qs = qs.filter(best_score__gte=MEDIUM_MIN_SCORE, best_score__lt=HIGH_MIN_SCORE)
    elif priority_filter == 'normal':
        qs = qs.filter(best_score__lt=MEDIUM_MIN_SCORE)

    qs = qs.prefetch_related(
        Prefetch(
            'anomaly_flags',
            queryset=AnomalyFlag.objects.filter(is_anomaly=True).order_by('-risk_score'),
            to_attr='anomaly_list',
        )
    )

    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    report_list = []
    for contract in page_obj:
        flag = contract.anomaly_list[0] if contract.anomaly_list else None
        if not flag:
            continue
        priority = _default_priority(flag.risk_score)
        has_report = InvestigationReport.objects.filter(contract=contract).exists()
        report_list.append({
            'contract_id': contract.contract_id,
            'title': contract.title[:70] + ('...' if len(contract.title) > 70 else ''),
            'entity': contract.entity.name if contract.entity else '—',
            'vendor': contract.vendor.name if contract.vendor else '—',
            'amount': contract.amount,
            'award_date': contract.award_date,
            'score': flag.risk_score,
            'priority': priority,
            'priority_label': _priority_label(priority),
            'has_report': has_report,
        })

    all_entities = ProcuringEntity.objects.filter(contracts__anomaly_flags__is_anomaly=True).distinct().order_by('name')

    context = {
        'report_list': report_list,
        'page_obj': page_obj,
        'total_count': paginator.count,
        'all_entities': all_entities,
        'current_search': search,
        'current_priority': priority_filter,
        'current_entity': entity_id,
    }
    return render(request, 'reports/report_list.html', context)


@login_required
def report_detail_view(request, contract_id):
    """Investigation Report — detailed document for a single flagged contract."""
    contract = get_object_or_404(
        Contract.objects.select_related('entity', 'vendor'),
        contract_id=contract_id
    )

    # A contract can have one flag per model (IF + LOF) — show the
    # highest-risk anomalous flag rather than assuming a single row.
    flag = (
        AnomalyFlag.objects.filter(contract=contract, is_anomaly=True)
        .order_by('-risk_score')
        .first()
    )
    has_anomaly = flag is not None

    feature = Feature.objects.filter(contract=contract).first()
    has_features = feature is not None

    if flag:
        explanation = Explanation.objects.filter(
            contract=contract, model_used=flag.model_used
        ).first()
    else:
        explanation = None

    # Get or list investigation reports
    reports = InvestigationReport.objects.filter(contract=contract).select_related('reviewer')
    latest_report = reports.first()

    priority = _default_priority(flag.risk_score) if flag else 'normal'
    priority_label = _priority_label(priority)

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
            ('Contract Value', float(feature.log_contract_value or 0), 'High' if feature.log_contract_value and float(feature.log_contract_value) > 15 else 'Moderate'),
            ('Single Bidder', 1.0 if feature.single_bidder_flag else 0.0, 'Moderate' if feature.single_bidder_flag else 'Lower'),
            ('Vendor Win Frequency', float(feature.vendor_win_frequency or 0), 'High' if feature.vendor_win_frequency and float(feature.vendor_win_frequency) > 0.05 else 'Lower'),
            ('Vendor Win Concentration', float(feature.vendor_win_concentration or 0), 'High' if feature.vendor_win_concentration and float(feature.vendor_win_concentration) > 0.5 else 'Lower'),
            ('Splitting Flag', 1.0 if feature.splitting_flag else 0.0, 'Moderate' if feature.splitting_flag else 'Lower'),
            ('Splitting Count', float(feature.splitting_count or 0), 'High' if feature.splitting_count and feature.splitting_count > 3 else 'Lower'),
        ]
        for name, value, level in feature_defs:
            contributions.append({
                'name': name,
                'value': value,
                'level': level,
                'bar_width': min(abs(value) * 100 / 20, 100) if value else 0,
                'direction': 'positive' if value > 0 else ('negative' if value < 0 else 'neutral'),
            })

    # NL explanation
    nl_explanation = explanation.natural_language if explanation else None
    if not nl_explanation and flag:
        parts = []
        if feature:
            if feature.single_bidder_flag:
                parts.append('only one bidder participated')
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
        'priority': priority,
        'priority_label': priority_label,
        'rank': rank,
        'total_anomalies': total_anomalies,
        'contributions': contributions,
        'nl_explanation': nl_explanation,
        'reports': reports,
        'latest_report': latest_report,
    }
    return render(request, 'reports/investigation_report.html', context)


@login_required
def report_create_view(request, contract_id):
    """Create an investigation report for a flagged contract."""
    contract = get_object_or_404(Contract, contract_id=contract_id)

    if request.method == 'POST':
        finding = request.POST.get('finding', '').strip()
        recommendation = request.POST.get('recommendation', '').strip()
        status = request.POST.get('status', 'draft')

        if status not in ('draft', 'reviewed'):
            status = 'draft'

        report = InvestigationReport.objects.create(
            contract=contract,
            reviewer=request.user,
            status=status,
            finding=finding,
            recommendation=recommendation,
        )
        messages.success(request, f'Investigation report {report.report_id} created.')
        return redirect('reporting:report_detail', contract_id=contract_id)

    return render(request, 'reports/report_create.html', {'contract': contract})
