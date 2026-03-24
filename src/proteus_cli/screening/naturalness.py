"""Antibody naturalness scoring via AbLang2 or Tamarind Bio."""
from __future__ import annotations


def score_naturalness(sequence: str, chain_type: str = "heavy") -> dict:
    """Score antibody sequence naturalness using AbLang2.

    Falls back gracefully if ablang2 is not installed.

    Args:
        sequence: Amino acid sequence (VH, VHH, or VL).
        chain_type: "heavy" or "light".

    Returns:
        dict with naturalness_score, interpretation, and install hint if needed.
    """
    try:
        import ablang2

        model = ablang2.pretrained(chain_type)
        # AbLang2 returns pseudo log-likelihood scores
        scores = model.pseudo_log_likelihood([sequence])
        score = float(scores[0]) if len(scores) > 0 else 0.0

        return {
            "naturalness_score": round(score, 4),
            "chain_type": chain_type,
            "interpretation": interpret_naturalness(score),
            "source": "ablang2_local",
        }
    except ImportError:
        return {
            "naturalness_score": None,
            "chain_type": chain_type,
            "warning": "Naturalness scoring skipped — ablang2 not installed",
            "screening_incomplete": True,
            "interpretation": (
                "AbLang2 not installed locally. Use Tamarind Bio's ablang tool "
                "instead (tamarind_screen_naturalness)."
            ),
            "source": "not_available",
            "install_hint": "pip install ablang2",
            "tamarind_alternative": (
                "Use tamarind_screen_naturalness MCP tool for cloud-based scoring"
            ),
        }
    except Exception as e:
        return {
            "naturalness_score": None,
            "error": str(e),
            "source": "error",
        }


def interpret_naturalness(score: float) -> str:
    """Interpret AbLang2 pseudo log-likelihood score."""
    # AbLang2 PLL scores: higher (less negative) = more natural
    # Typical ranges: natural antibodies -1 to -3, random sequences -5 to -8
    if score > -2.0:
        return "excellent — highly natural sequence"
    elif score > -3.0:
        return "good — within natural antibody distribution"
    elif score > -4.0:
        return "moderate — some unusual positions"
    elif score > -5.0:
        return "low — potentially unnatural, review CDR sequences"
    else:
        return "poor — likely unnatural, consider redesign"
