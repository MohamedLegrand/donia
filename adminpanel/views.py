from io import BytesIO, StringIO

from django.contrib import messages
from django.core.management import call_command
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from accounts.models import User
from donations.colors import category_color
from donations.models import Category, Donation, Need, Notification

from .decorators import admin_required
from .forms import CategoryForm

FR_MONTHS = ['', 'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']


@admin_required
def admin_dashboard_view(request):
    """Vue d'ensemble de la plateforme : indicateurs globaux et activité récente."""
    stats = {
        'total_users': User.objects.count(),
        'total_donateurs': User.objects.filter(role=User.Role.DONATEUR).count(),
        'total_responsables': User.objects.filter(role=User.Role.RESPONSABLE).count(),
        'pending_approvals': User.objects.filter(
            role=User.Role.RESPONSABLE, is_approved=False, onboarding_completed=True
        ).count(),
        'total_needs': Need.objects.count(),
        'active_needs': Need.objects.filter(is_closed=False).count(),
        'total_donations': Donation.objects.count(),
        'total_collected': Need.objects.aggregate(total=Sum('collected_amount'))['total'] or 0,
    }

    pending_preview = User.objects.filter(
        role=User.Role.RESPONSABLE, is_approved=False, onboarding_completed=True
    ).order_by('-date_joined')[:5]
    recent_donations = Donation.objects.select_related('donateur', 'need', 'need__orphanage').order_by('-created_at')[:5]
    recent_users = User.objects.order_by('-date_joined')[:5]

    context = {
        'stats': stats,
        'pending_preview': pending_preview,
        'recent_donations': recent_donations,
        'recent_users': recent_users,
    }
    return render(request, 'adminpanel/dashboard.html', context)


@admin_required
def users_list_view(request):
    """Gestion des utilisateurs : liste, recherche, filtre par rôle, activation/désactivation."""
    users = User.objects.all().order_by('-date_joined')

    role = request.GET.get('role', '')
    query = request.GET.get('q', '').strip()
    if role:
        users = users.filter(role=role)
    if query:
        users = users.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) |
            Q(email__icontains=query) | Q(orphanage_name__icontains=query)
        )

    paginator = Paginator(users, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'selected_role': role,
        'query': query,
        'role_choices': User.Role.choices,
    }
    return render(request, 'adminpanel/users_list.html', context)


@admin_required
def user_toggle_active_view(request, pk):
    """Active / désactive un compte utilisateur."""
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == 'POST' and user_obj != request.user:
        user_obj.is_active = not user_obj.is_active
        user_obj.save(update_fields=['is_active'])
        messages.success(
            request,
            f"Le compte de {user_obj.get_full_name() or user_obj.username} a été "
            f"{'réactivé' if user_obj.is_active else 'désactivé'}."
        )

    next_url = request.POST.get('next', '')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(next_url)
    return redirect('admin_users')


@admin_required
def pending_approvals_view(request):
    """Validation des comptes Responsable d'orphelinat en attente d'agrément."""
    pending_users = User.objects.filter(
        role=User.Role.RESPONSABLE, is_approved=False, onboarding_completed=True
    ).order_by('-date_joined')

    paginator = Paginator(pending_users, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'adminpanel/pending_approvals.html', {'page_obj': page_obj})


@admin_required
def approve_account_view(request, pk):
    """Valide le compte d'un responsable d'orphelinat."""
    user_obj = get_object_or_404(User, pk=pk, role=User.Role.RESPONSABLE)
    if request.method == 'POST':
        user_obj.is_approved = True
        user_obj.save(update_fields=['is_approved'])
        Notification.objects.create(
            user=user_obj,
            title="Compte validé",
            message="Votre compte responsable a été validé par un administrateur. Vous pouvez maintenant vous connecter.",
            level=Notification.Level.SUCCESS,
        )
        messages.success(request, f"Le compte de « {user_obj.orphanage_name or user_obj} » a été validé avec succès.")
    return redirect('admin_pending_approvals')


@admin_required
def reject_account_view(request, pk):
    """Rejette et supprime une demande d'inscription responsable en attente."""
    user_obj = get_object_or_404(User, pk=pk, role=User.Role.RESPONSABLE, is_approved=False)
    if request.method == 'POST':
        name = user_obj.orphanage_name or str(user_obj)
        user_obj.delete()
        messages.info(request, f"La demande d'inscription de « {name} » a été rejetée et supprimée.")
    return redirect('admin_pending_approvals')


@admin_required
def orphanages_list_view(request):
    """Supervision des orphelinats : besoins publiés et montants collectés par structure."""
    orphanages = User.objects.filter(role=User.Role.RESPONSABLE, organization_owner__isnull=True).annotate(
        needs_count=Count('needs', distinct=True),
        total_collected=Sum('needs__collected_amount'),
        team_size=Count('team_members', distinct=True),
    ).order_by('-date_joined')

    query = request.GET.get('q', '').strip()
    if query:
        orphanages = orphanages.filter(
            Q(orphanage_name__icontains=query) | Q(email__icontains=query) | Q(address__icontains=query)
        )

    paginator = Paginator(orphanages, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'adminpanel/orphanages_list.html', {'page_obj': page_obj, 'query': query})


@admin_required
def categories_list_view(request):
    """Gestion des catégories de besoins."""
    categories = Category.objects.annotate(needs_count=Count('needs')).order_by('name')
    return render(request, 'adminpanel/categories_list.html', {'categories': categories})


@admin_required
def category_create_view(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "La catégorie a été créée avec succès.")
            return redirect('admin_categories')
    else:
        form = CategoryForm()
    return render(request, 'adminpanel/category_form.html', {'form': form, 'is_edit': False})


@admin_required
def category_edit_view(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "La catégorie a été mise à jour avec succès.")
            return redirect('admin_categories')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'adminpanel/category_form.html', {'form': form, 'is_edit': True, 'category': category})


@admin_required
def category_delete_view(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        try:
            name = category.name
            category.delete()
            messages.success(request, f"La catégorie « {name} » a été supprimée.")
        except ProtectedError:
            messages.error(
                request,
                f"Impossible de supprimer « {category.name} » : des besoins publiés utilisent encore cette catégorie."
            )
    return redirect('admin_categories')


@admin_required
def donations_supervision_view(request):
    """Supervision globale de l'ensemble des dons effectués sur la plateforme."""
    donations = Donation.objects.select_related('donateur', 'need', 'need__orphanage').order_by('-created_at')

    status = request.GET.get('status', '')
    donation_type = request.GET.get('type', '')
    query = request.GET.get('q', '').strip()
    if status:
        donations = donations.filter(status=status)
    if donation_type:
        donations = donations.filter(donation_type=donation_type)
    if query:
        donations = donations.filter(
            Q(reference__icontains=query) | Q(donateur__email__icontains=query) |
            Q(need__title__icontains=query) | Q(need__orphanage__orphanage_name__icontains=query)
        )

    paginator = Paginator(donations, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'selected_status': status,
        'selected_type': donation_type,
        'query': query,
        'status_choices': Donation.Status.choices,
        'type_choices': Donation.DonationType.choices,
    }
    return render(request, 'adminpanel/donations_supervision.html', context)


@admin_required
def admin_statistics_view(request):
    """Statistiques consolidées de la plateforme."""
    stats = {
        'total_users': User.objects.count(),
        'total_donateurs': User.objects.filter(role=User.Role.DONATEUR).count(),
        'total_responsables': User.objects.filter(role=User.Role.RESPONSABLE).count(),
        'total_needs': Need.objects.count(),
        'total_donations': Donation.objects.count(),
        'total_collected': Need.objects.aggregate(total=Sum('collected_amount'))['total'] or 0,
    }

    total_collected = stats['total_collected']
    category_distribution = []
    if total_collected:
        cat_amounts = Donation.objects.filter(
            donation_type=Donation.DonationType.FINANCIER
        ).values('need__category__name').annotate(total=Sum('amount')).order_by('-total')
        for row in cat_amounts:
            category_distribution.append({
                'name': row['need__category__name'],
                'percentage': round((row['total'] / total_collected) * 100),
                'color': category_color(row['need__category__name']),
            })

    top_orphanages = list(
        User.objects.filter(role=User.Role.RESPONSABLE)
        .annotate(total_collected=Sum('needs__collected_amount'), needs_count=Count('needs', distinct=True))
        .filter(total_collected__gt=0)
        .order_by('-total_collected')[:5]
    )

    today = timezone.now().date()
    months = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    months.reverse()

    monthly_counts = Donation.objects.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id'))
    counts_map = {(row['month'].year, row['month'].month): row['count'] for row in monthly_counts if row['month']}
    monthly_trend = [{'label': FR_MONTHS[m], 'count': counts_map.get((y, m), 0)} for y, m in months]
    max_monthly = max([row['count'] for row in monthly_trend] + [0]) or 1

    context = {
        'stats': stats,
        'category_distribution': category_distribution,
        'top_orphanages': top_orphanages,
        'monthly_trend': monthly_trend,
        'max_monthly': max_monthly,
    }
    return render(request, 'adminpanel/statistics.html', context)


@admin_required
def notifications_management_view(request):
    """Consultation des notifications envoyées et diffusion d'une notification à un groupe d'utilisateurs."""
    if request.method == 'POST':
        target_role = request.POST.get('target_role', '')
        title = request.POST.get('title', '').strip()
        message = request.POST.get('message', '').strip()

        if title and message:
            target_users = User.objects.all()
            if target_role in (User.Role.DONATEUR, User.Role.RESPONSABLE):
                target_users = target_users.filter(role=target_role)

            Notification.objects.bulk_create([
                Notification(user=u, title=title, message=message, level=Notification.Level.INFO)
                for u in target_users
            ])
            messages.success(request, f"Notification envoyée à {target_users.count()} utilisateur(s).")
        else:
            messages.error(request, "Le titre et le message sont obligatoires.")
        return redirect('admin_notifications')

    notifications = Notification.objects.select_related('user').order_by('-created_at')
    paginator = Paginator(notifications, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'adminpanel/notifications_management.html', {'page_obj': page_obj})


@admin_required
def admin_reports_view(request):
    """Page d'accès au rapport global d'activité de la plateforme."""
    context = {
        'users_count': User.objects.count(),
        'needs_count': Need.objects.count(),
        'donations_count': Donation.objects.count(),
        'generated_at': timezone.now(),
    }
    return render(request, 'adminpanel/reports.html', context)


@admin_required
def download_admin_report_view(request):
    """Génère le rapport PDF global de la plateforme."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=18 * mm, rightMargin=18 * mm
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleDonia', parent=styles['Heading1'], textColor=rl_colors.HexColor('#0284c7'), fontSize=18)
    subtitle_style = ParagraphStyle('SubtitleDonia', parent=styles['Normal'], textColor=rl_colors.HexColor('#64748b'), fontSize=9)
    section_style = ParagraphStyle('SectionDonia', parent=styles['Heading2'], textColor=rl_colors.HexColor('#0f172a'), fontSize=12, spaceBefore=12, spaceAfter=6)

    elements = [
        Paragraph("Orphelink — Rapport global de la plateforme", title_style),
        Paragraph(f"Généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}", subtitle_style),
        Spacer(1, 8 * mm),
    ]

    total_collected = Need.objects.aggregate(total=Sum('collected_amount'))['total'] or 0
    summary_data = [
        ['Utilisateurs inscrits', str(User.objects.count())],
        ["dont Donateurs", str(User.objects.filter(role=User.Role.DONATEUR).count())],
        ["dont Responsables d'orphelinat", str(User.objects.filter(role=User.Role.RESPONSABLE).count())],
        ['Besoins publiés', str(Need.objects.count())],
        ['Dons enregistrés', str(Donation.objects.count())],
        ['Total collecté', f"{total_collected:,.0f} FCFA".replace(',', ' ')],
    ]
    summary_table = Table(summary_data, colWidths=[90 * mm, 70 * mm])
    summary_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), rl_colors.HexColor('#64748b')),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, rl_colors.HexColor('#e2e8f0')),
    ]))
    elements.append(summary_table)

    elements.append(Paragraph("Orphelinats les plus soutenus", section_style))
    top_orphanages = User.objects.filter(role=User.Role.RESPONSABLE).annotate(
        total_collected=Sum('needs__collected_amount'), needs_count=Count('needs', distinct=True)
    ).order_by('-total_collected')[:15]
    orph_data = [['Orphelinat', 'Besoins publiés', 'Total collecté (FCFA)']]
    for o in top_orphanages:
        orph_data.append([
            o.orphanage_name or str(o), str(o.needs_count), f"{(o.total_collected or 0):,.0f}".replace(',', ' ')
        ])
    if len(orph_data) == 1:
        orph_data.append(['Aucun orphelinat enregistré.', '', ''])
    orph_table = Table(orph_data, colWidths=[80 * mm, 40 * mm, 40 * mm], repeatRows=1)
    orph_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor('#0284c7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.4, rl_colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(orph_table)

    elements.append(Paragraph("Derniers dons enregistrés", section_style))
    recent_donations = Donation.objects.select_related('donateur', 'need').order_by('-created_at')[:30]
    don_data = [['Référence', 'Date', 'Donateur', 'Besoin', 'Montant / Détail']]
    for d in recent_donations:
        don_data.append([
            d.reference, d.created_at.strftime('%d/%m/%Y'),
            d.donateur.get_full_name() or d.donateur.username, d.need.title[:30], d.amount_display,
        ])
    if len(don_data) == 1:
        don_data.append(['Aucun don enregistré.', '', '', '', ''])
    don_table = Table(don_data, colWidths=[28 * mm, 20 * mm, 35 * mm, 42 * mm, 30 * mm], repeatRows=1)
    don_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor('#0284c7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.4, rl_colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(don_table)

    doc.build(elements)
    buffer.seek(0)
    filename = f"rapport_global_orphelink_{timezone.now().strftime('%Y%m%d')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename, content_type='application/pdf')


@admin_required
def backup_view(request):
    """Page d'accès à la sauvegarde des données de la plateforme."""
    return render(request, 'adminpanel/backup.html', {'generated_at': timezone.now()})


@admin_required
def download_backup_view(request):
    """Exporte l'ensemble des données métier de la plateforme au format JSON (sauvegarde)."""
    buffer = StringIO()
    call_command('dumpdata', 'accounts', 'donations', indent=2, stdout=buffer)
    data = buffer.getvalue()

    filename = f"sauvegarde_orphelink_{timezone.now().strftime('%Y%m%d_%H%M')}.json"
    response = HttpResponse(data, content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
