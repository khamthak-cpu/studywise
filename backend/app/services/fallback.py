from app.schemas import Source

MESSAGES = {
    "en": "I'm not sure about this from the textbook. Try rephrasing the question, "
          "or check the related chapter in your book.",
    "hi": "मुझे पाठ्यपुस्तक से इसका भरोसेमंद जवाब नहीं मिला। कृपया सवाल को दूसरे तरीके से पूछें "
          "या अपनी किताब का संबंधित अध्याय देखें।",
}


def is_confident(sources: list[Source], threshold: float) -> bool:
    return bool(sources) and (sources[0].score or 0.0) >= threshold


def relevant_only(sources: list[Source], threshold: float) -> list[Source]:
    """Drop weak chunks so they don't dilute the prompt."""
    return [s for s in sources if (s.score or 0.0) >= threshold - 0.1]


def fallback_message(language: str) -> str:
    return MESSAGES.get(language, MESSAGES["en"])