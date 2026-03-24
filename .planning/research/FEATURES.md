# Feature Landscape

**Domain:** HER2-targeted therapeutic antibodies
**Researched:** 2025-03-24

## Table Stakes

Features users expect. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| High-affinity HER2 binding | Clinical standard (nM range) | Medium | Trastuzumab ~5 nM; pertuzumab ~0.26 nM |
| Human/humanized frameworks | Reduced immunogenicity | Low | VH3/Vκ1 established; germline backtracking available |
| Mammalian expression | Clinical manufacturing | Medium | CHO/HEK293 standard; signal peptide optimization |
| Fc functionality | ADCC, CDC mechanisms | Low | Standard IgG1 Fc; proven therapeutic mechanism |
| Epitope characterization | Regulatory requirement | Medium | Domain mapping; competition studies required |

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multi-epitope targeting | Overcome resistance | High | Biparatopic like zanidatamab; enhanced efficacy |
| Enhanced internalization | Superior ADC potential | Medium | Non-dimerization blocking antibodies internalize better |
| Novel epitope targeting | Bypass existing resistance | High | Domain I/III regions; complementary to trastuzumab |
| Nanobody variants | Tissue penetration | Medium | Smaller format; faster clearance advantages |
| Cross-species reactivity | Preclinical utility | Low | Mouse/cynomolgus HER2 binding |

## Anti-Features

Features to explicitly NOT build. Common mistakes in this domain.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Single domain II targeting | Pertuzumab competition | Target domain IV + novel regions |
| Mouse frameworks | Immunogenicity risk | Use human germline VH3/Vκ1 |
| Low-affinity binders | Clinical failure precedent | Maintain sub-μM affinity minimum |
| Dimerization enhancers | Oncogenic risk | Focus on dimerization blocking |
| Non-internalizing formats | Poor ADC compatibility | Design for enhanced internalization |

## Feature Dependencies

```
Binding Affinity → Clinical Efficacy
    ↓
Epitope Selection → Resistance Profile
    ↓
Framework Choice → Expression Level → Manufacturing
    ↓
Fc Function → ADCC/CDC → Therapeutic Mechanism
    ↓
Internalization → ADC Potential → Enhanced Efficacy
```

**Critical Dependencies:**
- Epitope selection drives resistance profile and combination potential
- Framework choice determines expression and immunogenicity
- Internalization capacity affects ADC applications

## MVP Recommendation

For MVP, prioritize:
1. **High-affinity HER2 binding** (sub-μM KD requirement)
2. **VH3/Vκ1 human frameworks** (proven expression and safety)
3. **Domain IV epitope targeting** (established mechanism, trastuzumab-competitive or non-competitive)
4. **Enhanced internalization** (one key differentiator for ADC potential)

Defer to post-MVP:
- **Biparatopic engineering**: Complex but valuable for resistance
- **Novel epitope discovery**: High-risk but high-reward
- **Cross-species variants**: Nice-to-have for preclinical
- **Nanobody formats**: Alternative modality exploration

## Feature Priority Matrix

| Priority | Features | Rationale |
|----------|----------|-----------|
| P0 (Must-have) | High-affinity binding, Human frameworks, Mammalian expression | Clinical table stakes |
| P1 (Should-have) | Enhanced internalization, Epitope characterization, Fc function | Key differentiators |
| P2 (Could-have) | Multi-epitope targeting, Novel epitopes | Advanced features |
| P3 (Won't-have MVP) | Cross-species, Nanobody variants | Future development |

## Clinical Translation Considerations

| Feature | Clinical Value | Regulatory Path | Development Risk |
|---------|---------------|-----------------|------------------|
| Domain IV targeting | Established | Standard IND | Low |
| Biparatopic design | Enhanced efficacy | Complex CMC | Medium |
| Novel epitopes | Resistance bypass | Extensive preclinical | High |
| ADC-optimized | High therapeutic index | Combination IND | Medium |

## Sources

- Clinical landscape: Cancer Treatment Reviews 2024, Nature Communications 2023
- Feature validation: Frontiers in Immunology 2025, PMC studies on resistance
- Regulatory requirements: FDA guidance on therapeutic antibodies
- Technical feasibility: PDB structural studies, expression optimization papers