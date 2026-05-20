# Liability Rules — PTM and Sequence Motif Catalogue

Every PTM and sequence liability that the BY screening pipeline scans for, with the exact regex/algorithm used, severity classification, and triage notes. Authoritative source for `mcp__by-screening__screen_liabilities`.

Severity classification is a property of the **motif**. Location (CDR / interface / framework) determines the **action** taken (reject / flag / tolerate). See [filter-thresholds.md](filter-thresholds.md) for action thresholds.

---

## Deamidation (Asparagine → Aspartate / iso-Aspartate)

Asparagine residues followed by certain residues hydrolyze rapidly under physiological conditions, altering charge, structure, and immunogenicity.

| Motif | Regex | Severity | Half-life (37 °C, pH 7.4) | Notes |
|-------|-------|----------|---------------------------|-------|
| NG | `NG` | HIGH | ~1 day | Fastest deamidation rate; almost always problematic; reject if in CDR |
| NS | `NS` | MEDIUM | ~10 days | Solvent-exposure dependent; buried NS often acceptable |
| NT | `NT` | MEDIUM | ~10–30 days | Similar to NS; check accessibility |
| NA | `NA` | LOW | ~50+ days | Slow; monitor but do not reject on this alone |
| NH | `NH` | LOW | ~30 days | Less commonly flagged; included for completeness |

Algorithm: scan with each regex; emit a `Liability` record per match with type `deamidation`.

---

## Isomerization (Aspartate → iso-Aspartate)

Asp residues followed by small/flexible residues isomerize, disrupting backbone geometry.

| Motif | Regex | Severity | Notes |
|-------|-------|----------|-------|
| DG | `DG` | HIGH | Glycine provides no steric protection; rapid; reject in CDRs |
| DS | `DS` | MEDIUM | Slower than DG but still significant; flag in CDRs |
| DD | `DD` | LOW | Slow; advisory only |
| DH | `DH` | LOW | Slow; advisory only |

Algorithm: scan with each regex; emit a `Liability` record per match with type `isomerization`.

---

## Oxidation

| Residue | Regex | Severity | Notes |
|---------|-------|----------|-------|
| Methionine | `M` | MEDIUM | Sulfoxide formation; flag in CDR/interface; framework Met is lower risk |
| Tryptophan | `W` | LOW | Slower oxidation; flag only when in direct contact with target |
| Cysteine (unpaired) | see Free Cys section | HIGH | Reactive thiol; covered separately |

Algorithm: scan with each regex; emit per match. Note: every `M` and `W` in the sequence will be flagged — severity scaling and location triage filter these to actionable subset.

---

## Free Cysteines

Antibodies and most binders require an even number of cysteines so all form disulfide bonds. Odd count signals an unpaired Cys, which causes aggregation, dimerization (intermolecular disulfides), and oxidation.

Algorithm:
```
cys_count = sequence.count("C")
if cys_count % 2 != 0:
    emit Liability(type="free_cysteine", severity="high", motif=f"{cys_count} Cys")
```

Override: if the campaign explicitly engineers a free Cys (e.g., for site-specific conjugation), annotate it via `--allow-free-cys` and the position via CSV column `engineered_free_cys`. The screening pipeline will then skip the parity check.

Even-count designs should still verify disulfide pairings match the expected topology (e.g., antibody VH internal disulfide between C22-C92 Kabat) via structural inspection.

---

## N-linked Glycosylation

Eukaryotic N-glycosylation sequon is `N - X - S/T` where X is any residue except proline.

| Motif | Regex | Severity | Notes |
|-------|-------|----------|-------|
| NXS/T sequon | `N[^P][ST]` | MEDIUM (framework) / HIGH (CDR) | Glycan addition at binding site usually abolishes binding |

Algorithm: scan with regex; emit per match with type `glycosylation`. Severity escalation to HIGH applied at triage time if motif start falls inside a CDR.

---

## Aggregation-Prone Regions (APRs)

Stretches of hydrophobic residues that nucleate aggregation. The classical signature is 5+ consecutive residues from the highly hydrophobic set `{V, I, L, F, Y, W}` excluding any charged or proline-breaking residue.

Algorithm (simplified):
```
apr_regex = r"[VILFYW]{5,}"
for match in re.finditer(apr_regex, sequence):
    emit Liability(type="aggregation_prone_region", severity="medium",
                   motif=match.group(), position=match.start())
```

More sophisticated tools (TANGO, AGGRESCAN, Zyggregator) produce per-residue aggregation propensity scores; the BY default uses the regex above as a first pass and recommends external tools when structural coordinates are available. See `by-deploy-compute` for AGGRESCAN setup.

Severity:
- 5 consecutive: MEDIUM
- 7+ consecutive: HIGH
- In CDR / interface: escalate one severity level

---

## Polyspecificity Motifs

Empirically associated with nonspecific binding (polyreactivity), poor pharmacokinetics, and developability failure.

| Motif | Regex | Severity | Notes |
|-------|-------|----------|-------|
| RR cluster | `RR` | LOW | Doubly positive; if 3+ Arg within 5 residues, escalate to MEDIUM |
| RK cluster | `(RK\|KR)` | LOW | Doubly positive; same escalation rule |
| Highly positive CDR-H3 patch | sum(R,K,H over CDR-H3) >= 4 | MEDIUM | Correlates with polyreactivity per Jain et al. 2017 |
| Aromatic-rich CDR | count(F,W,Y in CDR) / CDR length > 0.30 | MEDIUM | Aromatic-rich CDRs bind nonspecifically |

Algorithm: regex scan for clusters; per-CDR composition for the patch-level checks.

---

## Severity Classification Summary

| Severity | Meaning | Default Action |
|----------|---------|----------------|
| HIGH | Strong evidence of accelerated degradation, binding loss, or developability failure | REJECT if in CDR; FLAG if in interface; TOLERATE in framework |
| MEDIUM | Moderate risk; context-dependent | FLAG if in CDR; document if in interface or framework |
| LOW | Mild risk; advisory only | Count toward soft ranking penalty (weight 1x) |

Location weights for ranking (applied to the *count* of liabilities, not severity directly):

| Location | Weight |
|----------|--------|
| CDR | 3x |
| Interface (non-CDR) | 2x |
| Framework | 1x |

`weighted_liability_count = sum(location_weight[L.location] for L in liabilities)`

---

## Implementation Reference

The canonical regex patterns and severity assignments live in `src/proteus_cli/screening/liabilities.py` and are exposed via the `mcp__by-screening__screen_liabilities` MCP tool. Do not duplicate the logic in scripts — call the MCP tool or import `proteus_cli.screening.liabilities.scan_liabilities()` directly.

If a new liability class is added, update:
1. The regex / algorithm in `liabilities.py`
2. This catalogue (severity + notes)
3. The default thresholds in [filter-thresholds.md](filter-thresholds.md)
4. The `THRESHOLDS` dict in `scripts/screen_batch.py` if the new liability participates in hard filters
