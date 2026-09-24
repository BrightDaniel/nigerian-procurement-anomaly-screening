from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoginForm, AdminUserCreateForm
from .decorators import administrator_required


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}.')
            return redirect('dashboard:index')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})


# ─── Admin-only views ───

@administrator_required
def user_list_view(request):
    User = get_user_model()
    users = User.objects.all().order_by('date_joined')
    return render(request, 'accounts/user_list.html', {'users': users})


@administrator_required
def user_create_view(request):
    User = get_user_model()
    if request.method == 'POST':
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'User "{user.username}" created successfully.')
            return redirect('admin_users')
    else:
        form = AdminUserCreateForm()
    return render(request, 'accounts/user_create.html', {'form': form})


@administrator_required
def user_edit_view(request, user_id):
    User = get_user_model()
    target_user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'toggle_active':
            if target_user == request.user:
                messages.error(request, 'You cannot deactivate your own account.')
            else:
                target_user.is_active = not target_user.is_active
                target_user.save()
                status = 'activated' if target_user.is_active else 'deactivated'
                messages.success(request, f'User "{target_user.username}" has been {status}.')
        return redirect('admin_user_edit', user_id=user_id)

    return render(request, 'accounts/user_edit.html', {'target_user': target_user})


@administrator_required
def settings_view(request):
    from apps.ingestion.models import Contract
    from apps.features.models import Feature
    from apps.detection.models import AnomalyFlag
    context = {
        'total_contracts': Contract.objects.count(),
        'total_features': Feature.objects.count(),
        'total_flags': AnomalyFlag.objects.count(),
        'total_flagged': AnomalyFlag.objects.filter(is_anomaly=True).count(),
    }
    return render(request, 'accounts/settings.html', context)
