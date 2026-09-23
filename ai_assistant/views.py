import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from donations.decorators import donateur_required

from .services import AIGenerationError, generate_chat_reply

MAX_MESSAGE_LENGTH = 800


@donateur_required
@require_POST
def chat_message_view(request):
    """Point d'entrée AJAX du chatbot d'aide aux donateurs."""
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': "Requête invalide."}, status=400)

    message = str(payload.get('message', '')).strip()
    history = payload.get('history', [])

    if not message:
        return JsonResponse({'error': "Le message ne peut pas être vide."}, status=400)
    if len(message) > MAX_MESSAGE_LENGTH:
        return JsonResponse({'error': f"Le message est trop long ({MAX_MESSAGE_LENGTH} caractères maximum)."}, status=400)
    if not isinstance(history, list):
        history = []

    try:
        reply = generate_chat_reply(history, message)
    except AIGenerationError as exc:
        return JsonResponse({'error': str(exc)}, status=502)

    return JsonResponse({'reply': reply})
