import json
import urllib.error
import urllib.request

from django.conf import settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


class AIGenerationError(Exception):
    """Erreur lors d'un appel à l'API Groq."""


def call_groq(messages, temperature=0.6, max_tokens=300):
    """Envoie une liste de messages (format OpenAI chat) à l'API Groq et retourne le texte généré."""
    if not settings.GROQ_API_KEY:
        raise AIGenerationError("La clé API Groq n'est pas configurée sur le serveur.")

    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode('utf-8')

    request = urllib.request.Request(
        GROQ_API_URL,
        data=payload,
        method='POST',
        headers={
            'Authorization': f'Bearer {settings.GROQ_API_KEY}',
            'Content-Type': 'application/json',
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        raise AIGenerationError(f"L'API Groq a renvoyé une erreur ({exc.code}) : {detail[:200]}") from exc
    except urllib.error.URLError as exc:
        raise AIGenerationError(f"Impossible de contacter l'API Groq : {exc.reason}") from exc

    try:
        return data['choices'][0]['message']['content'].strip()
    except (KeyError, IndexError) as exc:
        raise AIGenerationError("Réponse inattendue de l'API Groq.") from exc
