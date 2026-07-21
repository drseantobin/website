"""Assign Substack posts to the site's editorial categories."""
import re


CATEGORY_RULES = {
    "AI & Being Human": (
        "ai", "artificial intelligence", "agent", "algorithm", "automation",
        "chatbot", "machine", "technology", "digital", "internet", "robot",
        "software", "screen", "future", "superintelligence", "agi",
    ),
    "Deliverance & Spiritual Warfare": (
        "devil", "demon", "demonic", "exorc", "deliverance", "satan",
        "occult", "possession", "renunciation", "spiritual warfare",
        "curse", "witchcraft", "protection prayer", "spiritual battle",
    ),
    "Psychology & Healing": (
        "psycholog", "therap", "healing", "heal", "trauma", "grief",
        "anxiety", "depression", "attachment", "emotion", "mental health",
        "brain", "shame", "addiction", "pornography", "relationship",
    ),
    "Church & Culture": (
        "church", "catholic", "pope", "gospel", "rosary", "priest",
        "bible", "scripture", "liturgy", "culture", "society", "politic",
        "christmas", "easter", "saint", "vatican",
    ),
    "The Interior Life": (
        "prayer", "soul", "heart", "silence", "desert", "wilderness",
        "discern", "holiness", "faith", "god", "spiritual", "vocation",
        "interior", "presence", "conversion", "mercy",
    ),
}


def _score(text, terms):
    return sum(len(re.findall(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", text)) for term in terms)


def infer_category(post):
    """Return the strongest category, weighting the title and subtitle most."""
    title = (post.get("title") or "").lower()
    subtitle = (post.get("subtitle") or "").lower()
    description = (post.get("description") or "").lower()
    body = re.sub(r"<[^>]+>", " ", post.get("body_html") or "").lower()
    scores = {}
    for category, terms in CATEGORY_RULES.items():
        scores[category] = (
            _score(title, terms) * 5
            + _score(subtitle, terms) * 3
            + _score(description, terms) * 2
            + _score(body, terms)
        )
    return max(scores, key=scores.get) if max(scores.values()) else "The Interior Life"
