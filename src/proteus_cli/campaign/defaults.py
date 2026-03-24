"""Central defaults and smart tier selection for Proteus campaigns."""

# Recommended scaffolds by modality
RECOMMENDED_SCAFFOLDS = {
    "vhh": [
        {"name": "caplacizumab", "pdb": "7eow", "description": "Most widely used therapeutic nanobody, excellent framework stability"},
        {"name": "ozoralizumab", "pdb": "8z8v", "description": "Compact CDR3, good for smaller epitopes"},
    ],
    "scfv": [
        {"name": "adalimumab", "pdb": "6cr1", "description": "Top-selling antibody, extremely well-characterized framework"},
        {"name": "tezepelumab", "pdb": "5j13", "description": "Diverse CDR lengths, good for novel targets"},
    ],
    "de_novo_protein": [],  # No scaffolds needed
}

# All available scaffolds
ALL_SCAFFOLDS = {
    "vhh": [
        {"name": "caplacizumab", "pdb": "7eow"},
        {"name": "vobarilizumab", "pdb": "7xl0"},
        {"name": "gefurulimab", "pdb": "8coh"},
        {"name": "ozoralizumab", "pdb": "8z8v"},
        {"name": "gontivimab", "pdb": "gontivimab"},
        {"name": "isecarosmab", "pdb": "isecarosmab"},
        {"name": "sonelokimab", "pdb": "sonelokimab"},
    ],
    "scfv": [
        {"name": "adalimumab", "pdb": "6cr1"},
        {"name": "belimumab", "pdb": "5y9k"},
        {"name": "crenezumab", "pdb": "5vzy"},
        {"name": "dupilumab", "pdb": "6wgb"},
        {"name": "golimumab", "pdb": "5yoy"},
        {"name": "guselkumab", "pdb": "4m6m"},
        {"name": "mab1", "pdb": "3h42"},
        {"name": "necitumumab", "pdb": "6b3s"},
        {"name": "nirsevimab", "pdb": "5udc"},
        {"name": "sarilumab", "pdb": "8iow"},
        {"name": "secukinumab", "pdb": "6wio"},
        {"name": "tezepelumab", "pdb": "5j13"},
        {"name": "tralokinumab", "pdb": "5l6y"},
        {"name": "ustekinumab", "pdb": "3hmw"},
    ],
}

# Tier presets
DESIGN_TIERS = {
    "preview": {"num_designs": 500, "budget": 10, "alpha": 0.001, "description": "Quick feasibility (~$5 compute)"},
    "standard": {"num_designs": 5000, "budget": 50, "alpha": 0.001, "description": "Standard campaign per scaffold (~$35 compute)"},
    "production": {"num_designs": 20000, "budget": 100, "alpha": 0.001, "description": "Full production (~$140 compute)"},
    "exploratory": {"num_designs": 50000, "budget": 200, "alpha": 0.01, "description": "Novel/difficult targets (~$350 compute)"},
}

# Modality -> protocol mapping
MODALITY_PROTOCOLS = {
    "vhh": "nanobody-anything",
    "scfv": "antibody-anything",  # Fab template, convert to scFv post-design
    "de_novo_protein": "protein-anything",
}

# Cloud tools available per modality on Tamarind
# Both BoltzGen and PXDesign are available for de novo protein binders via
# Tamarind cloud. PXDesign is preferred when the target has a clear structure
# and defined epitope; BoltzGen is more flexible for unusual targets.
CLOUD_TOOLS = {
    "vhh": ["boltzgen"],
    "scfv": ["boltzgen"],
    "de_novo_protein": ["boltzgen", "pxdesign"],  # Both available on Tamarind
}

# Smart tier selection guidance
TIER_SELECTION_RULES = """
The agent should select tier based on:
- User says "quick test" or "preview" -> preview
- User gives a budget < $500 -> preview or standard
- User says "production" or "full campaign" -> production
- Target is novel/difficult (no known binders in SAbDab) -> exploratory
- Target is well-studied -> standard is sufficient
- User specifies number of designs -> use closest tier
- Multiple scaffolds: total = num_scaffolds x tier.num_designs
- De novo protein mode: increase num_designs 2x (harder problem)

Adjust alpha:
- Standard targets: 0.001 (quality-focused)
- Novel targets or diverse epitope: 0.01 (more exploration)
- User wants maximum diversity: 0.1
"""
