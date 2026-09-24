from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator

from apps.ingestion.models import Contract, ProcuringEntity
from apps.detection.models import AnomalyFlag
from apps.features.models import Feature
from apps.explainability.models import Explanation
from .models import InvestigationReport


def _default_priority(score):
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
def report_list_view(request):
    """Investigation Reports — flagged contracts with investigation status."""
    qs = (
        Contract.objects.filter(anomaly_flags__is_anomaly=True)
        .select_related('entity', 'vendor', 'anomaly_flags')
        .order_by('-anomaly_flags__risk_score')
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

    if priority_filter:
        if priority_filter == 'high':
            qs = qs.filter(anomaly_flags__risk_score__gte=Decimal('0.80'))
        elif priority_filter == 'medium':
            qs = qs.filter(anomaly_flags__risk_score__gte=Decimal('0.60'), anomaly_flags__risk_score__lt=Decimal('0.80'))
        elif priority_filter == 'normal':
            qs = qs.filter(anomaly_flags__risk_score__lt=Decimal('0.60'))

    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    report_list = []
    for contract in page_obj:
        flag = contract.anomaly_flags.order_by('-risk_score').first()
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

    try:
        flag = AnomalyFlag.objects.get(contract=contract)
        has_anomaly = True
    except AnomalyFlag.DoesNotExist:
        flag = None
        has_anomaly = False

    try:
        feature = Feature.objects.get(contract=contract)
        has_features = True
    except Feature.DoesNotExist:
        feature = None
        has_features = False

    try:
        explanation = Explanation.objects.get(contract=contract)
    except Explanation.DoesNotExist:
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
