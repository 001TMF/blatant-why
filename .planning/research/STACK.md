# Technology Stack

**Project:** HER2 Antibody Design Campaign
**Researched:** 2025-03-24

## Recommended Stack

### Core Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| VH3 Heavy Chain | Human germline | Primary scaffold | Proven success in trastuzumab/pertuzumab; excellent expression |
| Vκ1 Light Chain | Human germline | Primary scaffold | Validated pairing with VH3; optimal production levels |
| Tamarind Bio | Latest | Antibody design | 200+ models including HER2-specific; free tier available |

### Structural Analysis
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PDB Structures | Current | Epitope mapping | 1N8Z (trastuzumab), 6OGE (dual complex), 7MN8 (heterodimer) |
| AlphaFold | v3 | Structure prediction | High-confidence HER2 ECD structure available |
| ChimeraX | Latest | Visualization | Industry standard for antibody-antigen analysis |

### Design Platform
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Levitate Bio | Current | RFAntibody pipeline | Academic discount; specialized for antibody design |
| Local GPU | Optional | Power users | If PROTEUS_FOLD_DIR configured |

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| SAbDab | Current | Antibody database | Scaffold selection, sequence analysis |
| PDB | Current | Structural data | Epitope mapping, binding analysis |
| UniProt | Current | Sequence/annotation | HER2 functional domains, variants |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Heavy Chain | VH3 | VH1, VH4 | Lower success rate with HER2; production issues |
| Light Chain | Vκ1 | Vλ, other Vκ | Suboptimal pairing; reduced expression levels |
| Design Platform | Tamarind Bio | Local-only | Tamarind has HER2-specific training data |
| Target Format | Full-length IgG | Nanobody-only | Clinical precedent favors IgG for HER2 |

## Framework Rationale

### VH3/Vκ1 Selection
- **Trastuzumab precedent**: Uses VH3/Vκ1 framework with clinical success
- **Pertuzumab validation**: Also VH3/Vκ1, confirming framework compatibility
- **Production optimization**: Studies show highest expression levels with this pairing
- **Germline compatibility**: Minimal immunogenicity risk with human germlines

### Platform Selection
- **Tamarind Bio primary**: Free tier, HER2-specific models, no GPU requirements
- **Levitate Bio secondary**: Specialized RFAntibody pipeline for complex designs
- **Local GPU optional**: For teams with existing computational infrastructure

## Installation

```bash
# Core design platform access (cloud-based)
# Tamarind Bio: Web interface, no local installation
# Levitate Bio: Contact for academic access

# Structural analysis tools
pip install pymol-open-source
# ChimeraX: Download from UCSF website

# Database access
# SAbDab: Web interface at opig.stats.ox.ac.uk/webapps/sabdab-sabpred/sabdab
# PDB: Web interface at rcsb.org
# UniProt: Web interface at uniprot.org
```

## Sources

- VH/VL framework studies: Frontiers in Immunology 2018, 2020 (PMC5857972, PMC7700555)
- Trastuzumab structure: PDB 1N8Z, Science Advances 2024 (adu9945)
- Platform validation: Tamarind Bio documentation, Levitate Bio academic programs
- Production optimization: Effect of VH-VL Families study (HIGH confidence)