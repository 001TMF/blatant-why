# SARS-CoV-2 RBD VHH Nanobody Screening Gates

## Overview

This document defines comprehensive screening gates and success criteria for SARS-CoV-2 RBD VHH nanobody design campaigns. The screening pipeline employs a four-stage funnel approach with increasingly stringent criteria to identify optimal binders.

## Screening Pipeline Architecture

```
Raw Designs (1000+)
    ↓
Stage 1: Structure Prediction (→ ~300-400)
    ↓
Stage 2: Developability (→ ~100-150)
    ↓
Stage 3: Binding Interface (→ ~30-50)
    ↓
Stage 4: Diversity & Naturalness (→ ~10-15)
    ↓
Final Ranking & Selection
```

## Stage 1: Structure Prediction Screening

**Objective**: Filter for properly folded, structurally confident designs with good binding interfaces.

### Metrics & Thresholds

| Metric | Threshold | Interpretation | Tool |
|--------|-----------|----------------|------|
| **ipTM** | ≥ 0.5 | Interface predicted TM-score | `interpret_scores` |
| **ipSAE** | ≥ 0.3 | Interface predicted Structural Alignment Error | `interpret_scores` |
| **pLDDT** | ≥ 70 | Predicted Local Distance Difference Test | `interpret_scores` |
| **RMSD** | ≤ 3.5 Å | Root Mean Square Deviation (if available) | `screen_composite` |

### Scoring Rubric

- **ipTM ≥ 0.7**: Excellent structural confidence
- **ipTM 0.5-0.7**: Good structural confidence
- **ipTM < 0.5**: FAIL - Poor structural confidence

- **ipSAE ≥ 0.5**: Strong binding prediction
- **ipSAE 0.3-0.5**: Moderate binding potential
- **ipSAE < 0.3**: FAIL - Weak binding prediction

- **pLDDT ≥ 80**: Confident prediction
- **pLDDT 70-80**: Moderately confident
- **pLDDT < 70**: FAIL - Low confidence prediction

### Implementation
```python
def stage1_structure_screening(designs):
    passed = []
    for design in designs:
        score = screen_composite(
            sequence=design.sequence,
            iptm=design.iptm,
            ipsae=design.ipsae,
            plddt=design.plddt,
            rmsd=design.rmsd
        )
        if score['pass'] and all([
            design.iptm >= 0.5,
            design.ipsae >= 0.3,
            design.plddt >= 70
        ]):
            passed.append(design)
    return passed
```

## Stage 2: Developability Screening

**Objective**: Select designs with favorable drug-like properties and minimal liability risks.

### PTM Liability Analysis

| Liability Type | Severity Threshold | Max Count | Tool |
|----------------|-------------------|-----------|------|
| Deamidation (NG, NS, NT, NA) | High: 0, Medium: ≤2, Low: ≤4 | ≤6 total | `screen_liabilities` |
| Aspartate Isomerization (DG, DS) | High: 0, Medium: ≤1, Low: ≤2 | ≤3 total | `screen_liabilities` |
| Methionine Oxidation | Medium: ≤2, Low: ≤4 | ≤6 total | `screen_liabilities` |
| Tryptophan Oxidation | Any: ≤3 | ≤3 total | `screen_liabilities` |
| Free Cysteines | Any: 0 | 0 | `screen_liabilities` |

### Physicochemical Properties

| Property | Optimal Range | Threshold | Tool |
|----------|---------------|-----------|------|
| **Hydrophobic Fraction** | 0.25-0.40 | ≤0.45 | `screen_developability` |
| **Net Charge (pH 7.4)** | -2 to +8 | -5 to +10 | `screen_net_charge` |
| **Proline Fraction** | <0.08 | ≤0.10 | `screen_developability` |
| **Glycine Fraction** | 0.05-0.15 | ≤0.20 | `screen_developability` |
| **Total CDR Length** | 30-45 residues | ≤50 residues | `screen_developability` |

### VHH-Specific Criteria

| Property | VHH Threshold | Rationale |
|----------|---------------|-----------|
| **CDR3 Length** | 8-25 residues | VHH CDR3s are typically longer than conventional antibodies |
| **Disulfide Pattern** | 2 canonical + 0-1 additional | VHH domain structure requirements |
| **Hydrophobic CDRs** | CDR1/2: ≤40%, CDR3: ≤50% | Maintain solubility while allowing binding |

### Implementation
```python
def stage2_developability_screening(designs):
    passed = []
    for design in designs:
        liabilities = screen_liabilities(design.sequence)
        dev_assessment = screen_developability(
            sequence=design.sequence,
            cdr_regions=design.cdr_regions
        )
        charge = screen_net_charge(design.sequence, ph=7.4)

        # Count high-severity liabilities
        high_severity = sum(1 for l in liabilities if l['severity'] == 'high')
        medium_severity = sum(1 for l in liabilities if l['severity'] == 'medium')

        if all([
            high_severity == 0,
            medium_severity <= 3,
            len(liabilities) <= 12,
            dev_assessment['overall_risk'] != 'high',
            dev_assessment['hydrophobic_fraction'] <= 0.45,
            abs(charge['net_charge']) <= 10,
            dev_assessment['total_cdr_length'] <= 50
        ]):
            passed.append(design)
    return passed
```

## Stage 3: Binding Interface Analysis

**Objective**: Evaluate binding interface quality and shape complementarity.

### Interface Metrics

| Metric | Threshold | Description | Tool |
|--------|-----------|-------------|------|
| **Interface Contacts** | ≥15 | Atom-level contacts within 8Å | `screen_shape_complementarity` |
| **Contact Density** | ≥0.8 contacts/residue | Contacts per interface residue | `screen_shape_complementarity` |
| **Interface Size** | 12-25 residues | Total interface residues | `screen_shape_complementarity` |

### SARS-CoV-2 RBD Specific Considerations

| Criteria | Requirement | Rationale |
|----------|-------------|-----------|
| **Epitope Coverage** | ≥3 RBD hotspot residues | Target critical binding sites |
| **ACE2 Competition** | Overlap with ACE2 binding site | Neutralization mechanism |
| **Interface Hydrophobicity** | 30-60% hydrophobic contacts | Balance affinity and specificity |

### Implementation
```python
def stage3_interface_screening(designs, target_structure_path):
    passed = []
    for design in designs:
        # Requires structure prediction output
        structure_path = f"{design.output_dir}/structure.pdb"

        shape_comp = screen_shape_complementarity(
            structure_path=structure_path,
            design_chains=["A"],
            target_chains=["B"],
            contact_distance=8.0
        )

        if all([
            shape_comp['interface_contacts'] >= 15,
            shape_comp['contact_density'] >= 0.8,
            shape_comp['total_interface_residues'] >= 12,
            shape_comp['total_interface_residues'] <= 25
        ]):
            passed.append(design)
    return passed
```

## Stage 4: Diversity and Naturalness Screening

**Objective**: Ensure sequence diversity and natural-like properties in the final candidate set.

### Sequence Diversity

| Metric | Threshold | Tool |
|--------|-----------|------|
| **Pairwise Identity** | ≤90% within cluster | `screen_diversity` |
| **CDR3 Diversity** | ≤85% identity | `screen_align_sequences` |
| **Diversity Ratio** | ≥0.5 (clusters/sequences) | `screen_diversity` |

### Naturalness Assessment

| Metric | Threshold | Tool | Notes |
|--------|-----------|------|-------|
| **AbLang2 Score** | ≥-4.0 | `screen_naturalness` | Requires ablang2 installation |
| **Human-like Composition** | Framework regions: ≥95% identity to germline | Manual analysis | |

### Implementation
```python
def stage4_diversity_screening(designs, identity_threshold=0.9):
    # First pass: diversity clustering
    sequences_json = [
        {"name": d.name, "sequence": d.sequence} for d in designs
    ]

    diversity = screen_diversity(
        sequences_json=json.dumps(sequences_json),
        identity_threshold=identity_threshold
    )

    # Select representatives from each cluster
    if diversity['redundancy_warning']:
        # Apply stricter clustering
        diversity = screen_diversity(
            sequences_json=json.dumps(sequences_json),
            identity_threshold=0.8
        )

    # Second pass: naturalness scoring
    passed = []
    for design in designs:
        try:
            naturalness = screen_naturalness(
                sequence=design.sequence,
                chain_type="heavy"  # VHH is heavy chain
            )
            if naturalness.get('naturalness_score', -10) >= -4.0:
                passed.append(design)
        except:
            # Fallback if AbLang2 not available
            passed.append(design)

    return passed
```

## Composite Scoring System

### Weighted Scoring Formula

```
Composite Score = (
    0.30 × ipSAE_normalized +
    0.25 × ipTM_normalized +
    0.20 × (1 - liability_penalty) +
    0.15 × pLDDT_normalized +
    0.10 × interface_quality_normalized
)
```

### Normalization Functions

```python
def normalize_ipsae(ipsae):
    """Normalize ipSAE to 0-1 scale"""
    return min(1.0, max(0.0, ipsae / 0.8))

def normalize_iptm(iptm):
    """Normalize ipTM to 0-1 scale"""
    return min(1.0, max(0.0, (iptm - 0.3) / 0.7))

def liability_penalty(liabilities):
    """Calculate penalty based on liability count and severity"""
    penalty = 0
    for liability in liabilities:
        if liability['severity'] == 'high':
            penalty += 0.3
        elif liability['severity'] == 'medium':
            penalty += 0.1
        else:
            penalty += 0.05
    return min(1.0, penalty)
```

### Ranking Implementation

```python
def calculate_composite_score(design):
    score = (
        0.30 * normalize_ipsae(design.ipsae) +
        0.25 * normalize_iptm(design.iptm) +
        0.20 * (1 - liability_penalty(design.liabilities)) +
        0.15 * normalize_plddt(design.plddt) +
        0.10 * normalize_interface_quality(design.interface_contacts)
    )
    return score

def final_ranking(designs):
    """Apply composite scoring and Pareto optimization"""

    # Calculate composite scores
    for design in designs:
        design.composite_score = calculate_composite_score(design)

    # Pareto front analysis for multi-objective optimization
    pareto_designs = screen_pareto_front(
        designs_json=json.dumps([{
            "design_name": d.name,
            "ipsae_min": d.ipsae,
            "iptm": d.iptm,
            "liabilities": len(d.liabilities),
            "composite_score": d.composite_score
        } for d in designs])
    )

    # Combine Pareto ranking with composite scores
    final_ranking = sorted(designs,
                          key=lambda x: (-x.composite_score, x.pareto_rank))

    return final_ranking
```

## Quality Control Gates

### Automated QC Checks

1. **Structure Validation**
   - Verify all atoms present in predicted structures
   - Check for clashes or unrealistic geometries
   - Validate CDR loop conformations

2. **Sequence Validation**
   - Confirm VHH framework sequences
   - Validate disulfide connectivity
   - Check for unusual residue compositions

3. **Cross-Validation**
   - Compare predictions from multiple tools (BoltzGen vs Protenix)
   - Flag designs with high prediction disagreement
   - Require consensus for top candidates

### Manual Review Triggers

Designs requiring expert review:
- ipSAE > 0.6 but unusual CDR3 composition
- High liability count but excellent binding scores
- Novel CDR conformations not seen in training data
- Extreme physicochemical properties

## Implementation Workflow

### Screening Pipeline Execution

```python
def execute_screening_pipeline(raw_designs):
    """Execute complete screening pipeline"""

    print(f"Starting with {len(raw_designs)} designs")

    # Stage 1: Structure prediction screening
    stage1_passed = stage1_structure_screening(raw_designs)
    print(f"Stage 1 passed: {len(stage1_passed)} designs")

    # Stage 2: Developability screening
    stage2_passed = stage2_developability_screening(stage1_passed)
    print(f"Stage 2 passed: {len(stage2_passed)} designs")

    # Stage 3: Interface analysis
    stage3_passed = stage3_interface_screening(stage2_passed, target_structure)
    print(f"Stage 3 passed: {len(stage3_passed)} designs")

    # Stage 4: Diversity and naturalness
    stage4_passed = stage4_diversity_screening(stage3_passed)
    print(f"Stage 4 passed: {len(stage4_passed)} designs")

    # Final ranking
    final_candidates = final_ranking(stage4_passed)

    return final_candidates[:15]  # Top 15 for experimental validation
```

### Reporting and Visualization

```python
def generate_screening_report(designs, output_dir):
    """Generate comprehensive screening report"""

    # Export sequences
    campaign_export_fasta(output_dir, f"{output_dir}/final_candidates.fasta")

    # Export scores
    campaign_export_csv(output_dir, f"{output_dir}/screening_scores.csv")

    # Generate visualization scripts
    for design in designs[:5]:  # Top 5
        campaign_generate_visualization(
            structure_path=f"{design.output_dir}/structure.pdb",
            format="pymol",
            output_path=f"{output_dir}/viz_{design.name}.pml"
        )
```

## Success Criteria Summary

### Primary Success Metrics

1. **Binding Affinity Prediction**: ipSAE ≥ 0.4, ipTM ≥ 0.6
2. **Structural Quality**: pLDDT ≥ 75, RMSD ≤ 3.0 Å
3. **Developability**: ≤3 medium-severity liabilities, overall risk ≠ high
4. **Diversity**: ≥10 distinct sequences with ≤85% identity

### Campaign Success Thresholds

- **Minimum Success**: ≥5 candidates meeting all criteria
- **Good Success**: ≥10 candidates with composite score ≥0.7
- **Exceptional Success**: ≥15 candidates with ≥3 distinct epitopes

### Risk Mitigation

1. **Low Pass Rate (<20%)**: Use `screen_diagnose_failures` to identify bottlenecks
2. **High Redundancy**: Increase diversity parameters or scaffold variety
3. **Poor Binding Scores**: Adjust design parameters or target site selection
4. **High Liability Burden**: Implement liability-aware design constraints

---

*This screening protocol is optimized for SARS-CoV-2 RBD VHH campaigns but can be adapted for other targets by adjusting thresholds and target-specific criteria.*