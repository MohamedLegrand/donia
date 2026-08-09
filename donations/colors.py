# Couleur fixe par catégorie (assignée par identité, jamais par rang) pour que chaque
# catégorie garde toujours la même couleur d'un graphique à l'autre de la plateforme.
CATEGORY_COLORS = {
    'Santé & Médicaments': 'bg-red-500',
    'Nutrition & Alimentation': 'bg-emerald-500',
    'Éducation & Scolarité': 'bg-amber-500',
    'Hygiène & Vêtements': 'bg-violet-500',
    'Infrastructure & Logement': 'bg-sky-500',
}
DEFAULT_CATEGORY_COLOR = 'bg-slate-400'


def category_color(name):
    return CATEGORY_COLORS.get(name, DEFAULT_CATEGORY_COLOR)
