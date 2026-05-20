# Filter Thresholds — Master Reference

Single source of truth for every screening filter applied in the BY pipeline. Defaults map to the `production` profile in `scripts/screen_batch.py`. The `exploratory` and `strict` profiles shift specific values as noted.

All thresholds reflect Stage 1 hard filters unless explicitly marked "soft" (Stage 2 ranking input). Liability counts use the location-weighted scheme (CDR=3x, interface=2x, framework=1x) — see [liability-rules.md](liability-rules.md).

---

## Structural Confidence

| Filter | Metric | Default Threshold | Antibody Override | Nanobody Override | Binder (de novo) Override | Rationale | Reference |
|--------|--------|-------------------|-------------------|--------------------|--------------------------|-----------|-----------|
| Interface confidence | ipTM | >= 0.50 (PASS), >= 0.70 (preferred) | same | same | same | Below 0.50 the interface prediction is unreliable; reflects Protenix/AF3 confidence calibration | Evans et al. 2024 (AF3); BY-internal calibration |
| Global fold confidence | pTM | >= 0.50 advisory | same | same | same | High ipTM + low pTM = local interface looks plausible but the whole fold may be wrong | AF2/AF3 convention |
| Local plDDT (design chain mean) | pLDDT | >= 70 | same | same | same | Below 70 sidechains are unreliable; backbone may still be OK | Jumper et al. 2021 |
| CDR-H3 pLDDT | pLDDT_cdrh3 | n/a | >= 70 advisory | >= 60 advisory | n/a | Nanobody CDR-H3 is intrinsically flexible; relaxed threshold | BY-internal SAbDab analysis |
| Interface pLDDT | pLDDT (interface residues only) | >= 70 | same | same | same | Interface residues drive binding; whole-chain mean can mask local disorder | BY-internal |
| Refolding RMSD | CA-RMSD (Protenix re-fold of design) | <= 5.0 Å | <= 5.0 Å | <= 5.0 Å (CDR-H3 allowed up to 4.0 Å) | <= 3.5 Å | Self-consistency check; > 5 Å implies the design does not refold to its intended structure | BY-internal designability calibration |
| ipSAE-min | min(dt_ipsae, td_ipsae) | >= 0.40 | >= 0.40 | >= 0.35 | >= 0.45 | DunbrackLab open-source interface quality metric; symmetric stringency | Dunbrack et al. 2025 |

**Profile shifts:**

- `exploratory`: ipTM >= 0.40, RMSD <= 6.0 Å, ipSAE-min >= 0.30
- `strict`: ipTM >= 0.60, ipSAE-min >= 0.50, requires CONSENSUS in cross-validation

---

## Sequence Liabilities

| Filter | Metric | Default Threshold | Antibody | Nanobody | Binder | Rationale | Reference |
|--------|--------|-------------------|----------|----------|--------|-----------|-----------|
| Free cysteines | Cys count parity | even count (or annotated free Cys) | even | even (3 Cys allowed if VHH includes extra disulfide) | even (or annotated free) | Unpaired Cys causes aggregation, dimerization, oxidation | TAP Guideline 4 |
| CDR NG / DG motif | regex `NG` or `DG` in CDRs | 0 occurrences | 0 | 0 | n/a (no CDR concept) | NG = fast deamidation; DG = fast isomerization; both ruin binding sites within days | Robinson et al. 2017 |
| Total liability count (weighted) | weighted sum CDR=3x, interf=2x, fw=1x | <= 8 (soft) | <= 8 | <= 10 (CDRs are longer) | <= 6 | Soft penalty fed into composite ranking | BY-internal |
| Glycosylation in CDR | `N[^P][ST]` in CDR | 0 (soft FLAG) | 0 | 0 | n/a | N-linked glycan at binding site usually abolishes binding | TAP Guideline 5 |

See [liability-rules.md](liability-rules.md) for the full regex catalogue and severity matrix.

---

## Developability

| Filter | Metric | Default Threshold | Antibody | Nanobody | Binder | Rationale | Reference |
|--------|--------|-------------------|----------|----------|--------|-----------|-----------|
| Net charge at pH 7.4 | Henderson-Hasselbalch computed charge | -10 <= q <= +10 | same | same | same | Extreme charge drives viscosity, polyreactivity, poor PK | Raybould et al. 2019 (TAP) |
| Net charge (preferred) | same | -2 <= q <= +5 (soft) | same | same | same | Most clinical-stage antibodies fall in this band | TAP |
| Total CDR length | sum over all CDRs | <= 70 (Fv); <= 45 (VHH) | <= 70 | <= 45 | n/a | Long CDRs correlate with aggregation and poor manufacturability | TAP Guideline 1 |
| CDR-H3 length | residue count | <= 20 (Fv); <= 25 (VHH) | <= 20 | <= 25 | n/a | Above this is unusual; advisory FLAG | BY-internal SAbDab distribution |
| Hydrophobic fraction | count(AILMFWVP) / length | <= 0.55 (REJECT), <= 0.45 (FLAG) | same | same | <= 0.50 (REJECT) | TAP-style PSH (patches of surface hydrophobicity) proxy | TAP Guideline 2 |
| Hydrophobic patch area | DBSCAN on SAS hydrophobic atoms | single patch <= 600 Å² | same | same | <= 500 Å² | Large patches drive aggregation; structural input required | TAP Guideline 2 |
| Glycine fraction | count(G) / length | <= 0.15 (FLAG) | <= 0.15 | <= 0.18 | <= 0.12 | High Gly = floppy, possible design artifact | BY-internal |
| Proline fraction | count(P) / length | <= 0.10 (FLAG) | same | same | same | High Pro disrupts beta-sheets in framework | BY-internal |
| Single-residue diversity | max(count(AA))/length | <= 0.20 (FLAG) | same | same | same | Above 20% any single residue suggests degenerate design | BY-internal |
| Predicted Tm | ThermoMPNN or per-tool predicted melting temp | >= 60 °C (advisory) | same | same | same | Below 60 °C melting often means unstable in production conditions | See `by-deploy-compute` for ThermoMPNN setup |

---

## Cross-Validation Thresholds (Dual Predictor)

| Filter | Metric | CONSENSUS | DIVERGENT | REJECTED |
|--------|--------|-----------|-----------|----------|
| ipTM agreement | \|ipTM_a - ipTM_b\| | < 0.30 | 0.30 - 0.50 | > 0.50 |
| ipSAE agreement | both ipSAE_min > 0.30 | YES | one fails | both < 0.10 |
| Pose RMSD | CA-RMSD between predictor poses | < 3.0 Å | 3.0 - 5.0 Å | > 5.0 Å |

Cross-validation is REQUIRED for lab submission (`/by:approve-lab`) and is skipped only in exploratory iteration loops.

---

## Diversity / Clustering

| Filter | Metric | Default | Antibody | Nanobody | Binder | Rationale |
|--------|--------|---------|----------|----------|--------|-----------|
| Cluster identity | pairwise seq identity | 90% (CDR-only for Ab/VHH); 70% (full chain for binders) | 90% over CDRs | 90% over CDRs | 70% full chain | Avoid presenting near-identical designs as distinct candidates |
| Cluster representative | highest composite_score in cluster | same | same | same | same | Best-of-cluster selection |

---

## Profile Summary Matrix

| Profile | ipTM | pLDDT | RMSD | ipSAE-min | When |
|---------|------|-------|------|-----------|------|
| `exploratory` | >= 0.40 | >= 65 | <= 6.0 Å | >= 0.30 | First pass on novel target |
| `production` (default) | >= 0.50 | >= 70 | <= 5.0 Å | >= 0.40 | Standard campaign |
| `strict` | >= 0.60 | >= 75 | <= 3.5 Å | >= 0.50 | Lab-ready only; requires CONSENSUS cross-validation |

All thresholds map to the `THRESHOLDS` dict in `scripts/screen_batch.py`. Edits there must be mirrored in this document.
