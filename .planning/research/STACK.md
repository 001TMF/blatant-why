# Technology Stack for EGFR Antibody Design

**Project:** EGFR Therapeutic Antibody Design
**Researched:** 2026-03-24

## Recommended Stack

### Structural Analysis Tools
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PDB | 2024+ | Crystal structures (1YY9, 5SX4, 6B3S) | Essential for epitope mapping and resistance analysis |
| ChimeraX | Latest | Structure visualization | Superior for antibody-antigen complex analysis |
| PyMOL | 2.5+ | Structure analysis | Standard for structural biology workflows |

### Database Resources
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| UniProt | 2024 | Protein sequence/annotation | P00533 provides comprehensive EGFR data |
| SAbDab | Latest | Antibody structure database | Contains cetuximab, panitumumab structures |
| Thera-SAbDab | Latest | Therapeutic antibody tracking | WHO-recognized therapeutics database |

### Computational Design
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Tamarind Bio | Latest | Antibody design platform | Free tier, 200+ models, EGFR-specific data |
| AlphaFold | v3 | Protein structure prediction | High-confidence EGFR structure (AF_AFP00533F1) |
| Levitate Bio | Latest | RFAntibody pipeline | Academic discounts for design generation |

### Expression & Production
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Mammalian cells | CHO/HEK293 | Antibody production | Gold standard for therapeutic antibodies |
| E. coli | BL21(DE3) | EGFR domain expression | Established for domain III expression (literature) |
| Baculovirus | Sf9 cells | Complex glycoproteins | Alternative for full-length EGFR |

### Screening & Validation
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| SPR/BLI | Octet/Biacore | Binding kinetics | Standard for antibody characterization |
| Flow cytometry | FACS | Cell surface binding | Essential for EGFR+ cell lines |
| ELISA | Standard | Quantitative binding | High-throughput screening capability |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Design Platform | Tamarind Bio | Local GPU | Resource intensive, requires expertise |
| Expression | CHO cells | Yeast | Glycosylation differences affect function |
| Validation | SPR | MST | Less standardized protocols |

## Installation

```bash
# Core computational tools
pip install biopython pymol-open-source
conda install -c conda-forge mdanalysis

# Database access
pip install requests pandas
# SAbDab/UniProt API access via web interfaces

# Molecular visualization
# ChimeraX: Download from UCSF
# PyMOL: conda install -c schrodinger pymol
```

## Sources

- UniProt P00533: https://www.uniprot.org/uniprotkb/P00533/entry
- SAbDab: https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/sabdab
- PDB structures: 1YY9 (cetuximab), 5SX4 (panitumumab), 6B3S (necitumumab)
- Tamarind Bio platform documentation
- Established mammalian expression protocols for therapeutics