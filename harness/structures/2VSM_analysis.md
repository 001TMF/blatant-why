# Nipah Virus Glycoprotein G (2VSM) Analysis for VHH Nanobody Design

## Executive Summary

**Target:** Nipah virus attachment glycoprotein G in complex with human ephrin-B2 receptor
**PDB ID:** 2VSM
**Resolution:** Crystal structure
**Chains:** A (Nipah G, residues 188-602), B (Ephrin-B2, residues 28-165)
**Objective:** Design VHH nanobodies to block virus-receptor interaction

## Target Details

| Property | Value |
|----------|-------|
| **Target Protein** | Nipah virus attachment glycoprotein (NiV-G) |
| **UniProt ID** | Q9IH62 |
| **Chain A Range** | 188-602 (β-propeller, ephrin binding domain) |
| **Receptor** | Human ephrin-B2 (chain B, residues 28-165) |
| **Organism** | Nipah virus / Homo sapiens |
| **Function** | Viral attachment and entry receptor recognition |

## Structure Composition

| Chain | Protein | Residues | Atoms | Description |
|-------|---------|----------|-------|-------------|
| **A** | Nipah G | 188-602 | 3,349 | β-propeller domain with ephrin binding site |
| **B** | Ephrin-B2 | 28-165 | 1,108 | Receptor binding domain |

## Interface Analysis

**Total interface interactions:** 91 residue pairs (≤5.0Å)
**Chain A interface residues:** 35
**Chain B interface residues:** 33

### Critical Interface Residues (Chain A - Nipah G)

| Residue | Type | BSA Role | Classification |
|---------|------|----------|---------------|
| **389 TYR** | Polar anchor | High | Critical aromatic stacking |
| **402 ARG** | Salt bridge | High | Charged interaction with E97 |
| **504 TRP** | Core packing | Very High | Hydrophobic anchor |
| **581 TYR** | Polar anchor | High | H-bond network |
| **242 ARG** | Salt bridge | Medium | Charged rim contact |
| **491 SER** | H-bond | Medium | Polar network |
| **533 GLU** | Salt bridge | Medium | Charged interaction with K60/K116 |

### Key Ephrin-B2 Residues (Chain B)

| Residue | Type | Role | Notes |
|---------|------|------|-------|
| **125 TRP** | Hydrophobic | Core packing | Critical for binding |
| **120 PHE** | Hydrophobic | Core packing | Aromatic stacking |
| **116 LYS** | Charged | Salt bridge | Multiple interactions |
| **119 GLU** | Charged | H-bond network | Central polar contact |
| **108 ASP** | Charged | Salt bridge | Pairs with Y389 |

## Hotspot Identification for VHH Design

### Primary Hotspots (Essential for blocking)
- **Chain A Region 1:** 389-402 (TYR389, ARG402)
- **Chain A Region 2:** 504-507 (TRP504, GLY506, VAL507)
- **Chain A Region 3:** 579-583 (GLU579, ILE580, TYR581, THR583)

### Secondary Hotspots (Supporting contacts)
- **Chain A Region 4:** 238-242 (GLY238, SER239, CYS240, SER241, ARG242)
- **Chain A Region 5:** 530-533 (GLN530, THR531, ALA532, GLU533)
- **Chain A Region 6:** 555-559 (ASP555, THR556, ASN557, ALA558, GLN559)

## Recommended Targeting Strategy

### Epitope Definition for VHH Design

**Primary epitope (core blocking):**
```yaml
hotspots: [389, 402, 504, 506, 507, 581]
binding_site: "238-242,389-402,504-507,530-533,579-583"
target_chains: ["A"]
```

**Extended epitope (comprehensive blocking):**
```yaml
hotspots: [239, 389, 402, 491, 504, 533, 555, 557, 581]
binding_site: "238-242,305,388-389,401-402,458,488-492,501,504-507,530-533,555-559,579-583,588"
target_chains: ["A"]
```

## Existing Antibody Landscape (2025-2026 Research)

### Recent Breakthroughs
1. **DS90 Nanobody** (2025): Anti-fusion protein VHH with high potency
2. **m102.4 + DS90 Bispecific** (2025): Combined RBP + fusion targeting
3. **Peptide inhibitors** (2025): Computational peptides blocking ephrin interaction

### Gap Analysis
- **Current focus:** Fusion protein (F) targeting (DS90)
- **Opportunity:** Direct G protein ephrin-binding site blocking
- **Advantage:** Our approach targets the attachment step (upstream of fusion)

## VHH Design Recommendations

### Campaign Parameters
| Parameter | Recommended Value | Rationale |
|-----------|-------------------|-----------|
| **Modality** | VHH nanobody | Single-domain stability, smaller size |
| **Target** | Chain A epitope | Block virus-receptor binding |
| **Scaffolds** | caplacizumab, ozoralizumab | Proven stable VHH frameworks |
| **Campaign size** | 5,000 designs/scaffold | Standard production tier |
| **Protocol** | nanobody-anything | Generative VHH design |

### Design Strategy
1. **Primary approach:** Target the central ephrin-binding cavity
2. **Focus residues:** TRP504, TYR389, ARG402, TYR581 (essential contacts)
3. **Blocking mechanism:** Competitive inhibition of ephrin-B2/B3 binding
4. **CDR targeting:** CDR3 dominates binding to TRP504 pocket
5. **Size constraint:** Nanobody must fit in ephrin binding cavity

### Expected Challenges
1. **Deep binding pocket:** Requires long CDR3 for cavity penetration
2. **Conservation pressure:** Ephrin binding site is highly conserved
3. **Affinity requirement:** Must compete with nM ephrin binding
4. **Escape mutations:** Monitor for resistance in binding pocket

## Quality Thresholds

| Metric | Target | Excellent |
|--------|--------|-----------|
| **ipSAE** | >0.7 | >0.8 |
| **ipTM** | >0.8 | >0.9 |
| **Binding affinity** | <100 nM | <10 nM |
| **Blocking efficiency** | >80% | >95% |

## Next Steps

1. **Launch VHH campaign** targeting primary epitope (hotspots: 389,402,504,581)
2. **Screen for ephrin blocking** using competitive binding assays
3. **Validate top candidates** with neutralization assays
4. **Optimize affinity** through directed evolution if needed
5. **Test escape resistance** against known Nipah variants

---
*Analysis generated for VHH nanobody design campaign targeting Nipah virus entry*