"""Tests for ipSAE score computation and seed aggregation."""

from pathlib import Path

import numpy as np

from proteus_cli.scoring.ipsae import (
    _directional_ipsae,
    compute_ipsae,
    score_multi_seed,
)


def _expected_directional_score(min_pae_per_residue: np.ndarray, pae_cutoff: float) -> float:
    """Reproduce the directional ipSAE kernel for explicit test expectations."""
    good_mask = min_pae_per_residue < pae_cutoff
    n0 = int(np.sum(good_mask))
    if n0 == 0:
        return 0.0

    n0_clamped = max(n0, 19)
    d0 = 1.24 * (n0_clamped - 15) ** (1.0 / 3.0) - 1.8
    d0 = max(d0, 0.5)
    scores = 1.0 / (1.0 + (min_pae_per_residue / d0) ** 2)
    return float(scores[good_mask].mean())


def test_compute_ipsae_with_synthetic_asymmetric_pae_matrix():
    pae_matrix = np.array([
        [0.0, 0.0, 2.0, 12.0],
        [0.0, 0.0, 8.0, 4.0],
        [11.0, 1.0, 0.0, 0.0],
        [7.0, 9.0, 0.0, 0.0],
    ])
    chain_ids = np.array(["A", "A", "B", "B"])

    result = compute_ipsae(pae_matrix, chain_ids, design_chain="A", target_chain="B")

    expected_dt = _expected_directional_score(np.array([2.0, 4.0]), pae_cutoff=10.0)
    expected_td = _expected_directional_score(np.array([7.0, 1.0]), pae_cutoff=10.0)

    assert result["design_to_target_ipsae"] == round(expected_dt, 4)
    assert result["target_to_design_ipsae"] == round(expected_td, 4)
    assert result["ipsae_min"] == round(min(expected_dt, expected_td), 4)


def test_directional_ipsae_returns_zero_when_values_only_meet_cutoff():
    pae = np.array([
        [10.0, 12.0],
        [10.0, 15.0],
    ])
    from_mask = np.array([True, True])
    to_mask = np.array([True, True])

    result = _directional_ipsae(pae, from_mask, to_mask, pae_cutoff=10.0)

    assert result == 0.0


def test_directional_ipsae_uses_d0_floor_for_small_interfaces():
    pae = np.array([
        [0.25, 12.0],
        [11.0, 14.0],
    ])
    from_mask = np.array([True, True])
    to_mask = np.array([True, True])

    result = _directional_ipsae(pae, from_mask, to_mask, pae_cutoff=10.0)

    assert result == 0.8


def test_score_multi_seed_uses_requested_aggregation_mode(monkeypatch, tmp_path: Path):
    seed_paths = []
    for idx in range(4):
        path = tmp_path / f"seed_{idx}.npz"
        path.write_text("")
        seed_paths.append(str(path))

    scores_by_name = {
        "seed_0.npz": {"design_ipsae_min": 0.2},
        "seed_1.npz": {"design_ipsae_min": 0.5},
        "seed_2.npz": {"design_ipsae_min": 0.55},
        "seed_3.npz": {"design_ipsae_min": 0.9},
    }

    def fake_score_npz(npz_path, design_chain_ids, target_chain_ids, pae_cutoff):
        return dict(scores_by_name[Path(npz_path).name])

    monkeypatch.setattr("proteus_cli.scoring.ipsae.score_npz", fake_score_npz)

    best_result = score_multi_seed(seed_paths, aggregation="best")
    mean_result = score_multi_seed(seed_paths, aggregation="mean")
    median_result = score_multi_seed(seed_paths, aggregation="median")

    assert best_result["best_seed_idx"] == 3
    assert best_result["best_ipsae_min"] == 0.9

    assert mean_result["best_seed_idx"] == 2
    assert mean_result["best_ipsae_min"] == 0.55

    assert median_result["best_seed_idx"] == 1
    assert median_result["best_ipsae_min"] == 0.5

    for result in (best_result, mean_result, median_result):
        assert result["all_ipsae_min"] == [0.2, 0.5, 0.55, 0.9]
        assert result["mean_ipsae_min"] == 0.5375
        assert result["num_seeds"] == 4
        assert result["num_valid_seeds"] == 4
