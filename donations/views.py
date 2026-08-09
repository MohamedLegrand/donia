from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .colors import category_color
from .decorators import donateur_required
from .forms import DonationForm
from .models import Campaign, Category, Donation, Need, NeedFollow, Notification


@donateur_required
def dashboard_overview_view(request):
    """Vue d'ensemble du donateur : indicateurs, recommandations et activité récente."""
    user = request.user
    donations_qs = Donation.objects.filter(donateur=user).select_related(
        'need', 'need__category', 'need__orphanage'
    )

    supported_need_ids = donations_qs.values_list('need_id', flat=True).distinct()
    supported_needs = Need.objects.filter(id__in=supported_need_ids)

    total_amount = donations_qs.filter(
        donation_type=Donation.DonationType.FINANCIER
    ).aggregate(total=Sum('amount'))['total'] or 0

    stats = {
        'total_amount': total_amount,
        'orphanages_count': supported_needs.values('orphanage').distinct().count(),
        'children_impacted': supported_needs.aggregate(total=Sum('children_count'))['total'] or 0,
        'receipts_count': donations_qs.count(),
    }

    open_needs = list(
        Need.objects.filter(is_closed=False)
        .exclude(collected_amount__gte=F('target_amount'))
        .select_related('orphanage', 'category')
    )
    open_needs.sort(key=lambda n: n.priority_score, reverse=True)
    recommended_needs = open_needs[:3]

    recent_donations = donations_qs.order_by('-created_at')[:5]

    category_distribution = []
    if total_amount:
        cat_amounts = donations_qs.filter(
            donation_type=Donation.DonationType.FINANCIER
        ).values('need__category__name').annotate(total=Sum('amount')).order_by('-total')
        for row in cat_amounts:
            category_distribution.append({
                'name': row['need__category__name'],
                'percentage': round((row['total'] / total_amount) * 100),
                'color': category_color(row['need__category__name']),
            })

    context = {
        'stats': stats,
        'recommended_needs': recommended_needs,
        'recent_donations': recent_donations,
        'category_distribution': category_distribution,
    }
    return render(request, 'donations/overview.html', context)


@donateur_required
def needs_list_view(request):
    """Consultation et recherche multicritère des besoins ouverts."""
    needs = Need.objects.filter(is_closed=False).select_related('orphanage', 'category')

    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    urgency = request.GET.get('urgency', '')
    sort = request.GET.get('sort', 'priorite')

    if query:
        needs = needs.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(orphanage__orphanage_name__icontains=query)
        )
    if category_id:
        needs = needs.filter(category_id=category_id)

    needs = list(needs)
    if urgency:
        needs = [n for n in needs if n.priority_label == urgency]

    if sort == 'recent':
        needs.sort(key=lambda n: n.created_at, reverse=True)
    elif sort == 'couverture':
        needs.sort(key=lambda n: n.coverage_percent)
    else:
        needs.sort(key=lambda n: n.priority_score, reverse=True)

    paginator = Paginator(needs, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'categories': Category.objects.all(),
        'query': query,
        'selected_category': category_id,
        'selected_urgency': urgency,
        'selected_sort': sort,
    }
    return render(request, 'donations/needs_list.html', context)


@donateur_required
def need_detail_view(request, pk):
    """Détail d'un besoin avec formulaire de contribution."""
    need = get_object_or_404(Need.objects.select_related('orphanage', 'category'), pk=pk)
    form = DonationForm()
    is_following = NeedFollow.objects.filter(donateur=request.user, need=need).exists()
    return render(request, 'donations/need_detail.html', {'need': need, 'form': form, 'is_following': is_following})


@donateur_required
def toggle_follow_need_view(request, pk):
    """Ajoute ou retire un besoin des favoris suivis par le donateur."""
    need = get_object_or_404(Need, pk=pk)
    if request.method == 'POST':
        follow, created = NeedFollow.objects.get_or_create(donateur=request.user, need=need)
        if not created:
            follow.delete()
            messages.info(request, f"Vous ne suivez plus « {need.title} ».")
        else:
            messages.success(request, f"Vous suivez maintenant « {need.title} ». Vous serez notifié de sa progression.")

    next_url = request.POST.get('next') or reverse('need_detail', kwargs={'pk': need.pk})
    return redirect(next_url)


@donateur_required
def followed_needs_view(request):
    """Liste des besoins suivis (favoris) par le donateur."""
    follows = NeedFollow.objects.filter(donateur=request.user).select_related(
        'need', 'need__orphanage', 'need__category'
    ).order_by('-created_at')

    paginator = Paginator(follows, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'donations/followed_needs.html', {'page_obj': page_obj})


@donateur_required
def campaign_public_detail_view(request, pk):
    """Détail public d'une campagne et des besoins qui la composent."""
    campaign = get_object_or_404(Campaign.objects.select_related('orphanage'), pk=pk)
    needs = campaign.needs.select_related('category').order_by('-created_at')
    return render(request, 'donations/campaign_public_detail.html', {'campaign': campaign, 'needs': needs})


@donateur_required
def make_donation_view(request, pk):
    """Traitement du formulaire de don pour un besoin donné."""
    need = get_object_or_404(Need.objects.select_related('orphanage', 'category'), pk=pk, is_closed=False)

    if request.method != 'POST':
        return redirect('need_detail', pk=need.pk)

    form = DonationForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            donation = form.save(commit=False)
            donation.donateur = request.user
            donation.need = need
            donation.save()

            if donation.donation_type == Donation.DonationType.FINANCIER and donation.amount:
                Need.objects.filter(pk=need.pk).update(collected_amount=F('collected_amount') + donation.amount)
                need.refresh_from_db(fields=['collected_amount'])

            Notification.objects.create(
                user=request.user,
                title="Don enregistré avec succès",
                message=f"Merci ! Votre contribution pour « {need.title} » a été enregistrée (réf. {donation.reference}).",
                level=Notification.Level.SUCCESS,
                link=reverse('donation_history'),
            )
            Notification.objects.create(
                user=need.orphanage,
                title="Nouveau don reçu",
                message=f"{request.user.get_full_name() or request.user.username} a contribué au besoin « {need.title} ».",
                level=Notification.Level.INFO,
            )

            followers = NeedFollow.objects.filter(need=need).exclude(donateur=request.user).select_related('donateur')
            for follow in followers:
                Notification.objects.create(
                    user=follow.donateur,
                    title="Un besoin que vous suivez a progressé",
                    message=f"« {need.title} » vient de recevoir un nouveau don ({need.coverage_percent}% financé).",
                    level=Notification.Level.INFO,
                    link=reverse('need_detail', kwargs={'pk': need.pk}),
                )

        messages.success(
            request,
            f"Merci pour votre générosité ! Votre don {donation.reference} a été enregistré avec succès."
        )
        return redirect('donation_history')

    return render(request, 'donations/need_detail.html', {'need': need, 'form': form})


@donateur_required
def donation_history_view(request):
    """Historique complet des contributions du donateur."""
    donations = Donation.objects.filter(donateur=request.user).select_related(
        'need', 'need__orphanage', 'need__category'
    )

    status = request.GET.get('status', '')
    donation_type = request.GET.get('type', '')
    if status:
        donations = donations.filter(status=status)
    if donation_type:
        donations = donations.filter(donation_type=donation_type)

    paginator = Paginator(donations, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'selected_status': status,
        'selected_type': donation_type,
        'status_choices': Donation.Status.choices,
        'type_choices': Donation.DonationType.choices,
    }
    return render(request, 'donations/donation_history.html', context)


@donateur_required
def download_receipt_view(request, pk):
    """Génère et retourne le reçu de don officiel au format PDF."""
    donation = get_object_or_404(
        Donation.objects.select_related('need', 'need__orphanage'), pk=pk, donateur=request.user
    )

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    brand = colors.HexColor('#0284c7')
    slate = colors.HexColor('#334155')
    light = colors.HexColor('#64748b')

    p.setFillColor(brand)
    p.rect(0, height - 25 * mm, width, 25 * mm, fill=1, stroke=0)
    p.setFillColor(colors.white)
    p.setFont('Helvetica-Bold', 20)
    p.drawString(20 * mm, height - 16 * mm, "DONIA")
    p.setFont('Helvetica', 10)
    p.drawString(20 * mm, height - 21 * mm, "Plateforme de Gestion des Besoins et Dons des Orphelinats")

    p.setFillColor(slate)
    p.setFont('Helvetica-Bold', 16)
    p.drawString(20 * mm, height - 40 * mm, "Reçu de Don Officiel")

    p.setFont('Helvetica', 10)
    p.setFillColor(light)
    p.drawString(20 * mm, height - 47 * mm, f"Référence : {donation.reference}")
    p.drawString(20 * mm, height - 52 * mm, f"Date : {donation.created_at.strftime('%d/%m/%Y à %H:%M')}")

    box_top = height - 65 * mm
    box_height = 48 * mm
    p.setStrokeColor(colors.HexColor('#e2e8f0'))
    p.setFillColor(colors.HexColor('#f8fafc'))
    p.roundRect(20 * mm, box_top - box_height, width - 40 * mm, box_height, 3 * mm, fill=1, stroke=1)

    lines = [
        ("Donateur", donation.donateur.get_full_name() or donation.donateur.username),
        ("Email", donation.donateur.email),
        ("Orphelinat bénéficiaire", donation.need.orphanage.orphanage_name or str(donation.need.orphanage)),
        ("Besoin concerné", donation.need.title),
        ("Type de don", donation.get_donation_type_display()),
        ("Montant / Détail", donation.amount_display),
        ("Statut", donation.get_status_display()),
    ]
    ty = box_top - 8 * mm
    for label, value in lines:
        p.setFont('Helvetica-Bold', 9)
        p.setFillColor(light)
        p.drawString(25 * mm, ty, f"{label} :")
        p.setFont('Helvetica', 9)
        p.setFillColor(slate)
        p.drawString(70 * mm, ty, str(value))
        ty -= 6 * mm

    p.setFont('Helvetica-Oblique', 8)
    p.setFillColor(light)
    p.drawString(20 * mm, 20 * mm, "Ce document atteste de votre contribution solidaire via la plateforme DONIA.")
    p.drawString(20 * mm, 15 * mm, "Document généré automatiquement — ne nécessite pas de signature.")

    p.showPage()
    p.save()
    buffer.seek(0)

    return FileResponse(
        buffer, as_attachment=True,
        filename=f"recu_{donation.reference}.pdf",
        content_type='application/pdf'
    )


@login_required
def notifications_list_view(request):
    """Liste des notifications de l'utilisateur (donateur ou responsable) ; marquées comme lues à l'affichage."""
    notifications = Notification.objects.filter(user=request.user)
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    paginator = Paginator(notifications, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    template_name = (
        'donations/orphelinat_notifications.html' if request.user.is_responsable_role
        else 'donations/notifications.html'
    )
    return render(request, template_name, {'page_obj': page_obj})
