from django.db.models import F

from donations.models import Need

from .groq_client import AIGenerationError, call_groq

DESCRIPTION_SYSTEM_PROMPT = (
    "Tu rédiges des descriptions de besoins pour Orphelink, une plateforme mettant en relation "
    "des orphelinats et des donateurs. Écris un texte sobre, concret et sincère en français, "
    "de 3 à 5 phrases, qui explique le besoin, son contexte et son impact pour les enfants concernés. "
    "N'invente aucun chiffre ni fait non fourni. N'utilise ni markdown, ni émoji, ni titre : "
    "uniquement le texte de la description, prêt à être publié tel quel."
)

CHAT_SYSTEM_PROMPT = (
    "Tu es l'assistant IA d'Orphelink, une plateforme qui connecte des orphelinats à des donateurs "
    "pour financer des besoins concrets (santé, nutrition, éducation, logement...). "
    "Tu aides le donateur qui te parle à comprendre la plateforme et à choisir un besoin à soutenir. "
    "Réponds toujours en français, de façon chaleureuse, concise (4 phrases maximum sauf si on te "
    "demande plus de détails) et sans markdown. Voici un aperçu réel des besoins actuellement ouverts "
    "les plus urgents sur la plateforme : tu peux t'appuyer dessus pour recommander un besoin précis, "
    "mais n'invente jamais de besoin, d'orphelinat ou de chiffre qui n'y figure pas.\n\n{needs_snapshot}\n\n"
    "Si la question sort du cadre d'Orphelink (dons, besoins, orphelinats, fonctionnement du site), "
    "réponds poliment que tu es spécialisé dans l'aide aux donateurs Orphelink."
)

MAX_HISTORY_MESSAGES = 8


def generate_need_description(title, category_name, children_count, keywords):
    """Génère une description de besoin via l'IA, à partir des informations saisies par le responsable."""
    user_prompt_parts = [f"Titre du besoin : {title or 'non précisé'}"]
    if category_name:
        user_prompt_parts.append(f"Catégorie : {category_name}")
    if children_count:
        user_prompt_parts.append(f"Nombre d'enfants concernés : {children_count}")
    if keywords:
        user_prompt_parts.append(f"Éléments à mentionner : {keywords}")

    messages = [
        {"role": "system", "content": DESCRIPTION_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_prompt_parts)},
    ]
    return call_groq(messages, temperature=0.6, max_tokens=300)


def _build_needs_snapshot():
    """Résumé texte des besoins ouverts les plus urgents, pour ancrer les réponses du chatbot dans des données réelles."""
    open_needs = list(
        Need.objects.filter(is_closed=False)
        .exclude(collected_amount__gte=F('target_amount'))
        .select_related('orphanage', 'category')
    )
    open_needs.sort(key=lambda n: n.priority_score, reverse=True)
    top_needs = open_needs[:8]

    if not top_needs:
        return "Aucun besoin ouvert n'est disponible sur la plateforme pour le moment."

    lines = ["Besoins ouverts les plus urgents en ce moment :"]
    for need in top_needs:
        orphanage_name = need.orphanage.orphanage_name or str(need.orphanage)
        lines.append(
            f"- « {need.title} » ({need.category.name}, {orphanage_name}) — "
            f"{need.coverage_percent}% financé, urgence : {need.priority_label}"
        )
    return "\n".join(lines)


def generate_chat_reply(history, message):
    """Génère la réponse du chatbot donateur, en s'appuyant sur un aperçu réel des besoins ouverts."""
    system_prompt = CHAT_SYSTEM_PROMPT.format(needs_snapshot=_build_needs_snapshot())

    safe_history = [
        {"role": entry["role"], "content": entry["content"]}
        for entry in history
        if entry.get("role") in ("user", "assistant") and entry.get("content")
    ][-MAX_HISTORY_MESSAGES:]

    messages = [{"role": "system", "content": system_prompt}] + safe_history + [
        {"role": "user", "content": message}
    ]
    return call_groq(messages, temperature=0.5, max_tokens=350)


__all__ = ["AIGenerationError", "generate_need_description", "generate_chat_reply"]
