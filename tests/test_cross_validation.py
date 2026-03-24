"""Tests for cross-validation between dual structure predictors."""
from proteus_cli.screening.cross_validation import (
    classify_cross_validation,
    cross_validate_designs,
)


def test_classify_cross_validation_consensus_when_both_predictors_agree():
    status, confidence = classify_cross_validation(
        iptm_1=0.82,
        iptm_2=0.68,
        ipsae_1=0.55,
        ipsae_2=0.61,
    )

    assert status == "consensus"
    assert confidence == "high"


def test_classify_cross_validation_rejected_for_large_disagreement():
    status, confidence = classify_cross_validation(
        iptm_1=0.95,
        iptm_2=0.30,
        ipsae_1=0.65,
        ipsae_2=0.62,
    )

    assert status == "rejected"
    assert confidence == "low"


def test_classify_cross_validation_divergent_for_partial_agreement():
    status, confidence = classify_cross_validation(
        iptm_1=0.84,
        iptm_2=0.62,
        ipsae_1=0.48,
        ipsae_2=0.20,
    )

    assert status == "divergent"
    assert confidence == "medium"


def test_cross_validate_designs_marks_missing_scores_as_data_incomplete():
    results = cross_validate_designs([
        {
            "design_name": "design-incomplete",
            "boltzgen_iptm": 0.81,
            "boltzgen_ipsae": 0.52,
        }
    ])

    assert len(results) == 1
    result = results[0]
    assert result.design_name == "design-incomplete"
    assert result.status == "data_incomplete"
    assert result.confidence == "none"


def test_classify_cross_validation_accepts_iptm_delta_at_threshold():
    status, confidence = classify_cross_validation(
        iptm_1=0.80,
        iptm_2=0.50,
        ipsae_1=0.44,
        ipsae_2=0.47,
    )

    assert status == "consensus"
    assert confidence == "high"


def test_classify_cross_validation_accepts_ipsae_minimum_at_threshold():
    status, confidence = classify_cross_validation(
        iptm_1=0.76,
        iptm_2=0.50,
        ipsae_1=0.30,
        ipsae_2=0.30,
    )

    assert status == "consensus"
    assert confidence == "high"
