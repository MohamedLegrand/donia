from io import BytesIO

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .colors import category_color
from .decorators import responsable_required
from .forms import NeedForm
from .models import Donation, Need, Notification

FR_MONTHS = ['', 'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']


@responsable_required
def orphelinat_dashboard_view(request):
    """Vue d'ensemble du responsable : indicateurs, dons récents et besoins à prioriser."""
    user = request.user
    needs = Need.objects.filter(orphanage=user).select_related('category')
    donations = Donation.objects.filter(need__orphanage=user).select_related('need', 'donateur')

    stats = {
        'total_needs': needs.count(),
        'active_needs': needs.filter(is_closed=False).count(),
        'total_collected': needs.aggregate(total=Sum('collected_amount'))['total'] or 0,
        'donations_count': donations.count(),
        'pending_donations': donations.filter(status=Donation.Status.EN_ATTENTE).count(),
        'children_helped': needs.aggregate(total=Sum('children_count'))['total'] or 0,
    }

    urgent_needs = sorted(
        [n for n in needs if not n.is_closed], key=lambda n: n.priority_score, reverse=True
    )[:3]
    recent_donations = donations.order_by('-created_at')[:5]

    context = {
        'stats': stats,
        'urgent_needs': urgent_needs,
        'recent_donations': recent_donations,
    }
    return render(request, 'donations/orphelinat_overview.html', context)


@responsable_required
def my_needs_view(request):
    """Liste des besoins publiés par le responsable, avec actions de gestion."""
    needs = Need.objects.filter(orphanage=request.user).select_related('category').order_by('-created_at')

    status = request.GET.get('status', '')
    if status == 'ouverts':
        needs = needs.filter(is_closed=False)
    elif status == 'clotures':
        needs = needs.filter(is_closed=True)

    paginator = Paginator(needs, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'donations/my_needs.html', {'page_obj': page_obj, 'selected_status': status})


@responsable_required
def need_create_view(request):
    """Publication d'un nouveau besoin."""
    if request.method == 'POST':
        form = NeedForm(request.POST)
        if form.is_valid():
            need = form.save(commit=False)
            need.orphanage = request.user
            need.save()
            messages.success(request, f"Le besoin « {need.title} » a été publié avec succès.")
            return redirect('my_needs')
    else:
        form = NeedForm()

    return render(request, 'donations/need_form.html', {'form': form, 'is_edit': False})


@responsable_required
def need_edit_view(request, pk):
    """Modification d'un besoin existant appartenant au responsable connecté."""
    need = get_object_or_404(Need, pk=pk, orphanage=request.user)

    if request.method == 'POST':
        form = NeedForm(request.POST, instance=need)
        if form.is_valid():
            form.save()
            messages.success(request, "Le besoin a été mis à jour avec succès.")
            return redirect('my_needs')
    else:
        form = NeedForm(instance=need)

    return render(request, 'donations/need_form.html', {'form': form, 'is_edit': True, 'need': need})


@responsable_required
def need_delete_view(request, pk):
    """Suppression d'un besoin (action irréversible, confirmée côté template)."""
    need = get_object_or_404(Need, pk=pk, orphanage=request.user)
    if request.method == 'POST':
        title = need.title
        need.delete()
        messages.success(request, f"Le besoin « {title} » a été supprimé.")
    return redirect('my_needs')


@responsable_required
def need_toggle_close_view(request, pk):
    """Clôture / réouverture d'un besoin."""
    need = get_object_or_404(Need, pk=pk, orphanage=request.user)
    if request.method == 'POST':
        need.is_closed = not need.is_closed
        need.save(update_fields=['is_closed', 'updated_at'])
        messages.success(request, f"Le besoin a été {'clôturé' if need.is_closed else 'réouvert'}.")
    return redirect('my_needs')


@responsable_required
def received_donations_view(request):
    """Liste des dons reçus pour les besoins du responsable, avec validation de réception."""
    donations = Donation.objects.filter(need__orphanage=request.user).select_related(
        'need', 'donateur', 'need__category'
    )

    status = request.GET.get('status', '')
    if status:
        donations = donations.filter(status=status)

    paginator = Paginator(donations, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'selected_status': status,
        'status_choices': Donation.Status.choices,
    }
    return render(request, 'donations/received_donations.html', context)


@responsable_required
def validate_donation_view(request, pk):
    """Confirmation de la réception effective d'un don par le responsable."""
    donation = get_object_or_404(
        Donation.objects.select_related('need', 'donateur'), pk=pk, need__orphanage=request.user
    )

    if request.method == 'POST' and donation.status != Donation.Status.RECEPTIONNE:
        donation.status = Donation.Status.RECEPTIONNE
        donation.received_at = timezone.now()
        donation.save(update_fields=['status', 'received_at'])

        Notification.objects.create(
            user=donation.donateur,
            title="Don réceptionné par l'orphelinat",
            message=(
                f"Votre don {donation.reference} pour « {donation.need.title} » "
                "a bien été réceptionné. Merci pour votre générosité !"
            ),
            level=Notification.Level.SUCCESS,
            link=reverse('donation_history'),
        )
        messages.success(request, f"Le don {donation.reference} a été marqué comme réceptionné.")

    return redirect('received_donations')


@responsable_required
def statistics_view(request):
    """Statistiques consolidées : répartition par catégorie, besoins les plus soutenus, tendance mensuelle."""
    user = request.user
    needs = Need.objects.filter(orphanage=user).select_related('category')
    donations = Donation.objects.filter(need__orphanage=user).select_related('need__category')

    total_collected = needs.aggregate(total=Sum('collected_amount'))['total'] or 0
    stats = {
        'total_needs': needs.count(),
        'active_needs': needs.filter(is_closed=False).count(),
        'closed_needs': needs.filter(is_closed=True).count(),
        'total_collected': total_collected,
        'donations_count': donations.count(),
        'children_helped': needs.aggregate(total=Sum('children_count'))['total'] or 0,
    }

    category_distribution = []
    if total_collected:
        cat_amounts = donations.filter(
            donation_type=Donation.DonationType.FINANCIER
        ).values('need__category__name').annotate(total=Sum('amount')).order_by('-total')
        for row in cat_amounts:
            category_distribution.append({
                'name': row['need__category__name'],
                'percentage': round((row['total'] / total_collected) * 100),
                'color': category_color(row['need__category__name']),
            })

    top_needs = list(needs.order_by('-collected_amount')[:5])

    today = timezone.now().date()
    months = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    months.reverse()

    monthly_counts = donations.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id'))
    counts_map = {(row['month'].year, row['month'].month): row['count'] for row in monthly_counts if row['month']}

    monthly_trend = [{'label': FR_MONTHS[m], 'count': counts_map.get((y, m), 0)} for y, m in months]
    max_monthly = max([row['count'] for row in monthly_trend] + [0]) or 1

    context = {
        'stats': stats,
        'category_distribution': category_distribution,
        'top_needs': top_needs,
        'monthly_trend': monthly_trend,
        'max_monthly': max_monthly,
    }
    return render(request, 'donations/orphelinat_statistics.html', context)


@responsable_required
def reports_view(request):
    """Page d'accès au rapport d'activité téléchargeable au format PDF."""
    user = request.user
    context = {
        'needs_count': Need.objects.filter(orphanage=user).count(),
        'donations_count': Donation.objects.filter(need__orphanage=user).count(),
        'generated_at': timezone.now(),
    }
    return render(request, 'donations/orphelinat_reports.html', context)


@responsable_required
def download_report_view(request):
    """Génère le rapport d'activité PDF (besoins publiés + dons reçus)."""
    user = request.user
    needs = Need.objects.filter(orphanage=user).select_related('category').order_by('-created_at')
    donations = Donation.objects.filter(need__orphanage=user).select_related('need', 'donateur').order_by('-created_at')

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=18 * mm, rightMargin=18 * mm
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleDonia', parent=styles['Heading1'], textColor=rl_colors.HexColor('#0284c7'), fontSize=18)
    subtitle_style = ParagraphStyle('SubtitleDonia', parent=styles['Normal'], textColor=rl_colors.HexColor('#64748b'), fontSize=9)
    section_style = ParagraphStyle('SectionDonia', parent=styles['Heading2'], textColor=rl_colors.HexColor('#0f172a'), fontSize=12, spaceBefore=12, spaceAfter=6)

    elements = [
        Paragraph("DONIA — Rapport d'activité", title_style),
        Paragraph(
            f"{user.orphanage_name or user.get_full_name() or user.username} — "
            f"généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}",
            subtitle_style
        ),
        Spacer(1, 8 * mm),
    ]

    total_collected = needs.aggregate(total=Sum('collected_amount'))['total'] or 0
    summary_data = [
        ['Besoins publiés', str(needs.count())],
        ['Besoins actifs', str(needs.filter(is_closed=False).count())],
        ['Total collecté', f"{total_collected:,.0f} FCFA".replace(',', ' ')],
        ['Dons reçus', str(donations.count())],
        ['Enfants concernés', str(needs.aggregate(total=Sum('children_count'))['total'] or 0)],
    ]
    summary_table = Table(summary_data, colWidths=[80 * mm, 80 * mm])
    summary_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), rl_colors.HexColor('#64748b')),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, rl_colors.HexColor('#e2e8f0')),
    ]))
    elements.append(summary_table)

    elements.append(Paragraph("Besoins publiés", section_style))
    needs_data = [['Titre', 'Catégorie', 'Enfants', 'Cible (FCFA)', 'Collecté (FCFA)', 'Statut']]
    for n in needs:
        needs_data.append([
            n.title[:38], n.category.name, str(n.children_count),
            f"{n.target_amount:,.0f}".replace(',', ' '),
            f"{n.collected_amount:,.0f}".replace(',', ' '),
            'Clôturé' if n.is_closed else 'Actif',
        ])
    if len(needs_data) == 1:
        needs_data.append(['Aucun besoin publié pour le moment.', '', '', '', '', ''])
    needs_table = Table(needs_data, colWidths=[45 * mm, 30 * mm, 15 * mm, 25 * mm, 25 * mm, 20 * mm], repeatRows=1)
    needs_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor('#0284c7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.4, rl_colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(needs_table)

    elements.append(Paragraph("Dons reçus", section_style))
    donations_data = [['Référence', 'Date', 'Donateur', 'Besoin', 'Montant / Détail', 'Statut']]
    for d in donations[:50]:
        donations_data.append([
            d.reference, d.created_at.strftime('%d/%m/%Y'),
            d.donateur.get_full_name() or d.donateur.username,
            d.need.title[:28], d.amount_display, d.get_status_display(),
        ])
    if len(donations_data) == 1:
        donations_data.append(['Aucun don reçu pour le moment.', '', '', '', '', ''])
    donations_table = Table(
        donations_data, colWidths=[26 * mm, 20 * mm, 32 * mm, 34 * mm, 28 * mm, 25 * mm], repeatRows=1
    )
    donations_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor('#0284c7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.4, rl_colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(donations_table)

    doc.build(elements)
    buffer.seek(0)

    filename = f"rapport_donia_{timezone.now().strftime('%Y%m%d')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename, content_type='application/pdf')
