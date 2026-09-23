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

from accounts.forms import OrphanageOnboardingForm, TeamInviteForm
from accounts.models import TeamInvite, User

from .colors import category_color
from .decorators import approved_responsable_required, responsable_required
from .forms import CampaignForm, NeedForm, NeedPhotoForm
from .models import Campaign, Donation, Need, NeedPhoto, Notification

FR_MONTHS = ['', 'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']


@responsable_required
def orphelinat_dashboard_view(request):
    """Vue d'ensemble du responsable : indicateurs, dons récents et besoins à prioriser."""
    user = request.user.organization_account
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
def orphanage_onboarding_view(request):
    """Formulaire de complétion du profil de l'orphelinat (nom, adresse, justificatif, CNI)."""
    user = request.user

    if user.is_team_member:
        return redirect('orphelinat_dashboard')

    if request.method == 'POST':
        form = OrphanageOnboardingForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            onboarded_user = form.save(commit=False)
            onboarded_user.onboarding_completed = True
            onboarded_user.save()
            messages.success(
                request,
                "Merci ! Le profil de votre orphelinat a été soumis avec succès. "
                "Un administrateur va vérifier votre dossier avant de valider votre compte."
            )
            return redirect('orphelinat_dashboard')
    else:
        form = OrphanageOnboardingForm(instance=user)

    return render(request, 'donations/orphanage_onboarding.html', {'form': form})


@approved_responsable_required
def team_view(request):
    """Gestion de l'équipe : membres actuels et invitation de nouveaux membres."""
    if request.user.is_team_member:
        messages.error(request, "Seul le responsable principal peut gérer l'équipe.")
        return redirect('orphelinat_dashboard')

    if request.method == 'POST':
        form = TeamInviteForm(request.POST)
        if form.is_valid():
            invite = TeamInvite.objects.create(
                organization_owner=request.user,
                email=form.cleaned_data['email'],
            )
            invite_url = request.build_absolute_uri(
                reverse('team_invite_accept', kwargs={'token': invite.token})
            )
            messages.success(
                request,
                f"Invitation créée pour {invite.email}. Partagez-lui ce lien : {invite_url}"
            )
            return redirect('team_manage')
    else:
        form = TeamInviteForm()

    members = User.objects.filter(organization_owner=request.user).order_by('-date_joined')
    pending_invites = TeamInvite.objects.filter(organization_owner=request.user, is_used=False).order_by('-created_at')

    context = {
        'form': form,
        'members': members,
        'pending_invites': pending_invites,
    }
    return render(request, 'donations/team_manage.html', context)


@approved_responsable_required
def team_remove_member_view(request, pk):
    """Retire un membre de l'équipe (ne supprime pas son compte)."""
    if request.user.is_team_member:
        messages.error(request, "Seul le responsable principal peut gérer l'équipe.")
        return redirect('orphelinat_dashboard')

    member = get_object_or_404(User, pk=pk, organization_owner=request.user)
    if request.method == 'POST':
        member.organization_owner = None
        member.save(update_fields=['organization_owner'])
        messages.success(request, f"{member.get_full_name() or member.username} a été retiré(e) de l'équipe.")
    return redirect('team_manage')


@approved_responsable_required
def my_needs_view(request):
    """Liste des besoins publiés par le responsable, avec actions de gestion."""
    needs = Need.objects.filter(orphanage=request.user.organization_account).select_related('category').order_by('-created_at')

    status = request.GET.get('status', '')
    if status == 'ouverts':
        needs = needs.filter(is_closed=False)
    elif status == 'clotures':
        needs = needs.filter(is_closed=True)

    paginator = Paginator(needs, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'donations/my_needs.html', {'page_obj': page_obj, 'selected_status': status})


@approved_responsable_required
def need_create_view(request):
    """Publication d'un nouveau besoin."""
    org_user = request.user.organization_account

    if request.method == 'POST':
        form = NeedForm(request.POST, orphanage=org_user)
        if form.is_valid():
            need = form.save(commit=False)
            need.orphanage = org_user
            need.save()
            messages.success(request, f"Le besoin « {need.title} » a été publié avec succès.")
            return redirect('my_needs')
    else:
        form = NeedForm(orphanage=org_user)

    return render(request, 'donations/need_form.html', {'form': form, 'is_edit': False})


@approved_responsable_required
def need_edit_view(request, pk):
    """Modification d'un besoin existant appartenant au responsable connecté."""
    org_user = request.user.organization_account
    need = get_object_or_404(Need, pk=pk, orphanage=org_user)

    if request.method == 'POST':
        form = NeedForm(request.POST, instance=need, orphanage=org_user)
        if form.is_valid():
            form.save()
            messages.success(request, "Le besoin a été mis à jour avec succès.")
            return redirect('my_needs')
    else:
        form = NeedForm(instance=need, orphanage=org_user)

    return render(request, 'donations/need_form.html', {'form': form, 'is_edit': True, 'need': need})


@approved_responsable_required
def need_delete_view(request, pk):
    """Suppression d'un besoin (action irréversible, confirmée côté template)."""
    need = get_object_or_404(Need, pk=pk, orphanage=request.user.organization_account)
    if request.method == 'POST':
        title = need.title
        need.delete()
        messages.success(request, f"Le besoin « {title} » a été supprimé.")
    return redirect('my_needs')


@approved_responsable_required
def need_toggle_close_view(request, pk):
    """Clôture / réouverture d'un besoin."""
    need = get_object_or_404(Need, pk=pk, orphanage=request.user.organization_account)
    if request.method == 'POST':
        need.is_closed = not need.is_closed
        need.save(update_fields=['is_closed', 'updated_at'])
        messages.success(request, f"Le besoin a été {'clôturé' if need.is_closed else 'réouvert'}.")

        if need.is_closed:
            for follow in need.followers.select_related('donateur'):
                Notification.objects.create(
                    user=follow.donateur,
                    title="Un besoin que vous suivez a été clôturé",
                    message=f"« {need.title} » a été clôturé par l'orphelinat. Merci pour votre soutien !",
                    level=Notification.Level.SUCCESS,
                    link=reverse('need_detail', kwargs={'pk': need.pk}),
                )
    return redirect('my_needs')


@approved_responsable_required
def campaigns_list_view(request):
    """Liste des campagnes regroupant plusieurs besoins."""
    campaigns = Campaign.objects.filter(
        orphanage=request.user.organization_account
    ).annotate(needs_total=Count('needs')).order_by('-created_at')
    return render(request, 'donations/campaigns_list.html', {'campaigns': campaigns})


@approved_responsable_required
def campaign_create_view(request):
    """Création d'une nouvelle campagne."""
    if request.method == 'POST':
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.orphanage = request.user.organization_account
            campaign.save()
            messages.success(request, f"La campagne « {campaign.title} » a été créée avec succès.")
            return redirect('campaigns_list')
    else:
        form = CampaignForm()

    return render(request, 'donations/campaign_form.html', {'form': form, 'is_edit': False})


@approved_responsable_required
def campaign_edit_view(request, pk):
    """Modification d'une campagne existante."""
    campaign = get_object_or_404(Campaign, pk=pk, orphanage=request.user.organization_account)

    if request.method == 'POST':
        form = CampaignForm(request.POST, instance=campaign)
        if form.is_valid():
            form.save()
            messages.success(request, "La campagne a été mise à jour avec succès.")
            return redirect('campaigns_list')
    else:
        form = CampaignForm(instance=campaign)

    return render(request, 'donations/campaign_form.html', {'form': form, 'is_edit': True, 'campaign': campaign})


@approved_responsable_required
def campaign_delete_view(request, pk):
    """Suppression d'une campagne (les besoins associés sont conservés, simplement détachés)."""
    campaign = get_object_or_404(Campaign, pk=pk, orphanage=request.user.organization_account)
    if request.method == 'POST':
        title = campaign.title
        campaign.delete()
        messages.success(request, f"La campagne « {title} » a été supprimée. Ses besoins restent publiés.")
    return redirect('campaigns_list')


@approved_responsable_required
def campaign_toggle_close_view(request, pk):
    """Clôture / réouverture d'une campagne."""
    campaign = get_object_or_404(Campaign, pk=pk, orphanage=request.user.organization_account)
    if request.method == 'POST':
        campaign.is_closed = not campaign.is_closed
        campaign.save(update_fields=['is_closed', 'updated_at'])
        messages.success(request, f"La campagne a été {'clôturée' if campaign.is_closed else 'réouverte'}.")
    return redirect('campaigns_list')


@approved_responsable_required
def need_photos_view(request, pk):
    """Galerie photo d'un besoin : ajout et suppression de photos."""
    need = get_object_or_404(Need, pk=pk, orphanage=request.user.organization_account)

    if request.method == 'POST':
        form = NeedPhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.need = need
            photo.save()
            messages.success(request, "La photo a été ajoutée avec succès.")
            return redirect('need_photos', pk=need.pk)
    else:
        form = NeedPhotoForm()

    return render(request, 'donations/need_photos.html', {'need': need, 'form': form})


@approved_responsable_required
def need_photo_delete_view(request, pk, photo_pk):
    """Suppression d'une photo d'un besoin."""
    need = get_object_or_404(Need, pk=pk, orphanage=request.user.organization_account)
    photo = get_object_or_404(NeedPhoto, pk=photo_pk, need=need)
    if request.method == 'POST':
        photo.delete()
        messages.success(request, "La photo a été supprimée.")
    return redirect('need_photos', pk=need.pk)


@approved_responsable_required
def received_donations_view(request):
    """Liste des dons reçus pour les besoins du responsable, avec validation de réception."""
    donations = Donation.objects.filter(need__orphanage=request.user.organization_account).select_related(
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


@approved_responsable_required
def validate_donation_view(request, pk):
    """Confirmation de la réception effective d'un don par le responsable."""
    donation = get_object_or_404(
        Donation.objects.select_related('need', 'donateur'), pk=pk, need__orphanage=request.user.organization_account
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


@approved_responsable_required
def statistics_view(request):
    """Statistiques consolidées : répartition par catégorie, besoins les plus soutenus, tendance mensuelle."""
    user = request.user.organization_account
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


@approved_responsable_required
def reports_view(request):
    """Page d'accès au rapport d'activité téléchargeable au format PDF."""
    user = request.user.organization_account
    context = {
        'needs_count': Need.objects.filter(orphanage=user).count(),
        'donations_count': Donation.objects.filter(need__orphanage=user).count(),
        'generated_at': timezone.now(),
    }
    return render(request, 'donations/orphelinat_reports.html', context)


@approved_responsable_required
def download_report_view(request):
    """Génère le rapport d'activité PDF (besoins publiés + dons reçus)."""
    user = request.user.organization_account
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
        Paragraph("Orphelink — Rapport d'activité", title_style),
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

    filename = f"rapport_orphelink_{timezone.now().strftime('%Y%m%d')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename, content_type='application/pdf')
