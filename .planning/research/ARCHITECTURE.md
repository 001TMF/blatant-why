# Architecture Patterns

**Domain:** HER2-targeted antibody therapeutics
**Researched:** 2025-03-24

## Recommended Architecture

```
HER2 Antibody System Architecture:

Target: HER2/ERBB2 Extracellular Domain (630 AA)
├── Domain I (1-165): Membrane-proximal, novel epitopes
├── Domain II (166-310): Dimerization arm, pertuzumab epitope
├── Domain III (311-480): Membrane-distal, novel epitopes
└── Domain IV (481-630): Trastuzumab epitope, ligand binding

Antibody Formats:
├── Full-length IgG: Clinical standard (trastuzumab, pertuzumab)
├── Biparatopic IgG: Enhanced efficacy (zanidatamab)
├── scFv fragments: Research/ADC applications
└── Nanobodies: Novel penetration/half-life profiles
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| VH Domain | Heavy chain antigen binding | VL domain, Fc region |
| VL Domain | Light chain antigen binding | VH domain |
| CH1/CL | Framework structure | Antigen binding domains |
| Hinge Region | Flexibility, proteolysis site | Heavy chains |
| Fc Region | Effector functions (ADCC/CDC) | Immune system cells |
| CDR Loops | Specific HER2 epitope recognition | HER2 extracellular domains |

### Data Flow

**Binding Cascade:**
1. CDR loops recognize HER2 epitope
2. Framework provides structural stability
3. Hinge allows conformational flexibility
4. Fc mediates immune effector functions
5. Internalization enables ADC payload delivery

## Patterns to Follow

### Pattern 1: Domain-Specific Targeting
**What:** Target distinct HER2 domains for complementary mechanisms
**When:** Designing for resistance prevention or enhanced efficacy
**Example:**
```
Domain II (Pertuzumab-like): Block heterodimerization
Domain IV (Trastuzumab-like): Block homodimerization + ADCC
Combined: Enhanced receptor blocking
```

### Pattern 2: Biparatopic Design
**What:** Single antibody molecule targeting two epitopes
**When:** Need enhanced internalization and avidity
**Example:**
```
Zanidatamab architecture:
- Fab arm 1: Domain II epitope
- Fab arm 2: Domain IV epitope
- Result: Enhanced clustering and CDC
```

### Pattern 3: Framework Consistency
**What:** Use proven VH3/Vκ1 framework combination
**When:** Optimizing for expression and clinical translation
**Example:**
```typescript
// Successful framework pattern
Heavy: VH3 germline (IGHV3-23*01 or similar)
Light: Vκ1 germline (IGKV1-39*01 or similar)
CDR grafting onto these frameworks
```

### Pattern 4: Internalization Optimization
**What:** Design for enhanced receptor internalization
**When:** Developing ADC-compatible antibodies
**Example:**
```
Non-dimerization-blocking epitopes (Groups 2-4):
- Target domains I, III, or specific regions of II/IV
- Avoid direct dimerization interface
- Result: Enhanced internalization vs dimerization blockers
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Single-Epitope Dependence
**What:** Relying solely on one epitope (e.g., only domain IV)
**Why bad:** Resistance through HER2 mutations or expression changes
**Instead:** Multi-epitope or complementary targeting strategy

### Anti-Pattern 2: Novel Framework Experimentation
**What:** Using untested antibody frameworks for HER2
**Why bad:** Unknown expression, stability, immunogenicity profiles
**Instead:** Leverage proven VH3/Vκ1 framework success

### Anti-Pattern 3: Ignoring Dimerization Biology
**What:** Designing without considering HER2 heterodimerization
**Why bad:** Miss key mechanism of action and resistance
**Instead:** Explicitly design for dimerization blocking or alternative mechanisms

### Anti-Pattern 4: Pure Affinity Optimization
**What:** Optimizing only for highest binding affinity
**Why bad:** May compromise function, expression, or developability
**Instead:** Balance affinity with functional activity and expression

## Scalability Considerations

| Concern | At Research Scale | At Preclinical Scale | At Clinical Scale |
|---------|-------------------|---------------------|-------------------|
| Expression | HEK293 transient | CHO stable lines | cGMP manufacturing |
| Purification | Protein A capture | Multi-step purification | Validated process |
| Characterization | Binding + expression | Full biophysical | ICH Q6B compliance |
| Screening | 96-well ELISA | Flow cytometry + internalization | GLP/GMP assays |

## Format-Specific Architectures

### Full-Length IgG (Recommended for Clinical)
```
Advantages:
- Established manufacturing
- Long half-life (21 days)
- Fc-mediated effector functions
- Regulatory precedent

Architecture:
- 2 heavy chains (VH-CH1-hinge-CH2-CH3)
- 2 light chains (VL-CL)
- Disulfide bonds: inter-heavy, heavy-light
```

### Biparatopic IgG (Advanced Design)
```
Advantages:
- Enhanced avidity
- Improved internalization
- Complement activation

Architecture:
- Asymmetric Fab arms
- Different CDRs in each Fab
- Single Fc region
- Complex but proven (zanidatamab)
```

### scFv Fragments (Research/ADC)
```
Advantages:
- Smaller size (25-30 kDa)
- Better tumor penetration
- Flexible linker design

Architecture:
- VH-linker-VL (or VL-linker-VH)
- 15-20 AA flexible linker
- Optional C-terminal tags/fusions
```

### Nanobodies (Alternative Format)
```
Advantages:
- Very small (12-15 kDa)
- High stability
- Excellent tissue penetration

Architecture:
- Single VHH domain
- Extended CDR3 loop
- Camelid framework adapted
```

## Manufacturing Considerations

### Expression Systems
- **Mammalian (CHO/HEK293)**: Required for clinical; proper glycosylation
- **Bacterial (E.coli)**: Research only; Fab/scFv formats possible
- **Yeast**: Alternative for research; some glycosylation

### Process Scalability
- **Research**: Transient transfection sufficient
- **Preclinical**: Stable cell line development
- **Clinical**: cGMP-compliant manufacturing required

## Sources

- Structural architecture: PDB 1N8Z, 6OGE, 7MN8 crystal structures
- Biparatopic design: Zanidatamab clinical studies, Nature Communications 2023
- Framework patterns: VH-VL family studies, Frontiers in Immunology 2018
- Manufacturing: Industry standard antibody production protocols
- Internalization: PMC3984328 study on HER2 antibody internalization mechanisms