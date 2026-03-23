# Skill: Proteus Epitope Analysis

You are an expert structural biologist performing epitope analysis and hotspot
residue selection for protein and antibody binder design. This skill covers
interface identification, residue classification, hotspot scoring, and
producing residue selections for proteus-prot or proteus-ab input.

---

## 1. Using pdb_interface_residues to Identify the Binding Interface

Use the PDB MCP tools in sequence to obtain and analyze the interface:

1. `pdb_search` -- find a co-crystal structure of the target with a known binder.
   Prefer resolution < 3.0 A, X-ray or cryo-EM.
2. `pdb_get_chains` -- identify which chain is the target antigen and which is
   the binder (antibody heavy/light chain or protein partner).
3. `pdb_download` -- download the structure as CIF for downstream tools.
4. `pdb_interface_residues` -- detect contact residues between two chains.

Call the interface tool with target and binder chains:
```
pdb_interface_residues(pdb_id="7S4S", chain1="A", chain2="H", distance_cutoff=5.0)
```

Returns: `chain1_residues` and `chain2_residues` (each a list of `{resname, resseq}`),
plus `contact_count` (total heavy-atom contact pairs). The `resseq` values are
`label_seq_id` -- use these directly for hotspot specification.

**Distance cutoff guidance:**

| Cutoff | Use case |
|--------|----------|
| 4.0 A  | Strict direct contacts (H-bonds, salt bridges) |
| 5.0 A  | Standard analysis (default, recommended) |
| 6.0 A  | Extended interface with second-shell packing |
| 8.0 A  | Broad epitope mapping with solvent-mediated contacts |

Start at 5.0 A. If contact count < 20, widen to 6.0 A. If > 200, tighten to
4.0 A. Always run at both 5.0 A and 4.0 A -- residues present at both cutoffs
are the deeply buried core.

---

## 2. Residue Classification

Classify each interface residue into one of four functional categories:

### Buried contact
Fully enclosed in the interface, present at both 4.0 A and 6.0 A cutoffs.
Typically Ala, Val, Leu, Ile, Ser, Thr with high contact counts. These define
the geometric footprint -- excellent hotspot candidates.

### Core packing (hydrophobic contacts)
Hydrophobic residues (Leu, Ile, Val, Phe, Trp, Met, Ala, Pro) in the interface
interior making contacts with multiple partner residues. Critical for binding
energy. A cluster of 2-4 hydrophobic packers almost always contains a hotspot.

### Polar anchor (H-bonds, salt bridges)
Polar/charged residues (Asp, Glu, Lys, Arg, Asn, Gln, His, Ser, Thr, Tyr)
forming directional interactions. Look for charge-complementary pairs
(Asp--Lys, Glu--Arg). Tyr is dual-role: hydroxyl H-bond + aromatic packing.
Polar anchors provide specificity over nonspecific hydrophobic collapse.
Prioritize when they coincide with buried positions.

### Hydrophobic core (central aromatic/aliphatic)
The highest-contact-density subset: Trp, Phe, Tyr, and central Leu/Ile in the
top 10-15% by contact count. Often spatially clustered (2-3 aromatics within
6 A). These are the most energetically important residues per the "O-ring"
model. Always include at least one in your hotspot selection.

---

## 3. Hotspot Scoring Using Contact Analysis

### Count contacts per residue
Run interface analysis at both 5.0 A and 4.0 A. Residues present at both
cutoffs are more buried and higher-scoring. Count unique partner residues
each target residue contacts (its "degree" in the contact graph).

### Prioritize mixed interaction types

| Priority | Profile | Examples |
|----------|---------|----------|
| Highest  | Polar anchor + buried + high contacts | Tyr, Arg, Asn at center |
| High     | Hydrophobic core + high contacts | Trp, Phe with 5+ partners |
| Medium   | Buried + moderate contacts | Leu, Val, Ile in the core |
| Lower    | Rim polar, few partners | Peripheral Lys, Glu at edge |

Residues with mixed interaction types (e.g., Tyr making both ring-stacking and
H-bond contacts) score higher than single-type residues at the same count.

### Identify anchor residues
Rank all target interface residues by contact count descending. The top 3-5
are anchors. Verify they cluster within 8-10 A of each other. If top residues
are scattered, focus on the largest connected cluster. Anchors contribute
40-60% of total binding energy and are the non-negotiable core of selection.

---

## 4. Recommending Hotspot Residues for Design Input

### Output format
Express hotspots as chain ID + `label_seq_id` matching `resseq` from
`pdb_interface_residues`:

- **proteus-prot**: `hotspot_residues: ["A45", "A72", "A98", "A101", "A156"]`
- **proteus-ab**: `epitope_residues: ["A45", "A72", "A98", "A101", "A156"]`

### How many hotspots to select

| Interface size | Hotspot count | Rationale |
|---------------|---------------|-----------|
| Small (< 800 A^2, < 15 residues) | 3-4 | Most of the interface is essential |
| Medium (800-1500 A^2, 15-30 residues) | 5-6 | Focus on the energetic core |
| Large (> 1500 A^2, > 30 residues) | 6-8 | Select the dominant patch |

Fewer than 3 gives too little constraint. More than 8 over-constrains backbone
sampling and reduces diversity.

### Balance between buried and surface-exposed
Target 60-70% buried/core residues (energetic foundation) and 30-40% polar
anchors at the rim (specificity handles). All-hydrophobic selections risk
nonspecific binding. All-polar selections lack binding energy.

### Spatial contiguity check
All hotspots must be within 12-15 A of at least one other hotspot (C-alpha
distance). Drop isolated residues (> 15 A from nearest neighbor) in favor
of spatially connected alternatives. The patch should span 15-25 A in its
longest dimension.

---

## 5. Shape Complementarity Assessment

### Interface area considerations
Estimate from residue count: each interface residue contributes ~40-60 A^2 of
buried surface area.

- **Small (< 800 A^2):** Nanobody or small binder. Use proteus-ab with
  nanobody-anything protocol.
- **Medium (800-1500 A^2):** Standard territory. Use proteus-prot (extended)
  or proteus-ab (antibody-anything).
- **Large (> 1500 A^2):** May need multi-domain or bispecific. Consider
  splitting into sub-patches.

### Convex vs concave targets

**Concave (pocket/groove):** Residues cluster in a narrow band with several
deeply buried high-contact residues. Proteus-prot excels -- RFdiffusion
generates complementary convex protrusions. Place hotspots at pocket bottom.

**Convex (dome/ridge):** Residues spread broadly with few deeply buried
contacts. Antibody CDR loops wrap convex surfaces well. Prefer proteus-ab.
Emphasize polar anchors capping the convexity and aromatics packing the dome.

**Flat:** Many residues with similar moderate contacts, large area, no dominant
cluster. Either tool works. Use larger hotspot sets (6-8) distributed across
the patch with 2+ polar anchors at edges.

---

## 6. Example Workflow

Complete epitope analysis for a PD-L1 binder design:

**Step 1 -- Load target:**
```
pdb_search(query="PD-L1 pembrolizumab complex", max_results=5)
```
Select best resolution (e.g. 5JXE at 2.15 A).

**Step 2 -- Get chains:**
```
pdb_get_chains(pdb_id="5JXE")
```
Identify: chain A = PD-L1 (target), chain H = heavy chain, chain L = light.

**Step 3 -- Analyze interface:**
```
pdb_interface_residues(pdb_id="5JXE", chain1="A", chain2="H", distance_cutoff=5.0)
pdb_interface_residues(pdb_id="5JXE", chain1="A", chain2="H", distance_cutoff=4.0)
```
Residues in both results are the buried core.

**Step 4 -- Classify and score each target residue:**
- Ile54: Hydrophobic core, buried at 4.0 A, high contacts
- Tyr56: Polar anchor + aromatic packing, both cutoffs
- Glu58: Polar anchor, salt bridge potential
- Asp61: Polar anchor, charge-complementary
- Asn63: Polar anchor, H-bond network
- Val68: Core packing, buried, moderate contacts

**Step 5 -- Select hotspots:**
Top 3 anchors by contact density: Tyr56, Ile54, Glu58. Add supporting
residues for coverage: Asp61, Asn63, Val68. Verify contiguity and balance:
2 hydrophobic (Ile54, Val68) + 4 polar (Tyr56, Glu58, Asp61, Asn63).

Final: `["A54", "A56", "A58", "A61", "A63", "A68"]`

**Step 6 -- Feed to design tool:**

For de novo binder (see `proteus-prot` skill for full YAML spec):
```bash
# Write YAML config
cat > /tmp/pdl1_config.yaml << 'EOF'
target:
  file: /tmp/5JXE.cif
  chains:
    A:
      hotspots: [54, 56, 58, 61, 63, 68]
binder_length: 80
EOF

# Run PXDesign
PROTENIX_DATA_ROOT_DIR=$PROTEUS_PROT_DIR/release_data/ccd_cache \
TOOL_WEIGHTS_ROOT=$PROTEUS_PROT_DIR/tool_weights \
pxdesign pipeline --preset extended -i /tmp/pdl1_config.yaml -o /tmp/pdl1_design --N_sample 30 --dtype bf16
```

For antibody design (see `proteus-ab` skill for full entities spec):
```bash
# Write entities YAML
cat > /tmp/pdl1_spec.yaml << 'EOF'
entities:
- file:
    path: /tmp/5JXE.cif
    include:
    - chain:
        id: A
    binding_types:
    - chain:
        id: A
        binding: 54..58,61..63,68
EOF

# Run Proteus-AB
PROTEUS_MODELS_DIR=~/.cache/proteus-ab LAYERNORM_TYPE=openfold \
proteus-ab run /tmp/pdl1_spec.yaml --protocol nanobody-anything --num_designs 50 --budget 10 --output /tmp/pdl1_ab
```

---

## Decision Checklist

Before finalizing an epitope analysis:

- [ ] Resolution adequate (< 3.0 A preferred)
- [ ] Correct chains identified (target vs binder)
- [ ] Interface analyzed at 5.0 A and 4.0 A cutoffs
- [ ] Each residue classified (buried, core packing, polar anchor, hydrophobic core)
- [ ] Residues ranked by contact density and interaction diversity
- [ ] 3-8 hotspots selected with 60-70% buried / 30-40% polar balance
- [ ] Spatial contiguity confirmed (all within 12-15 A of a neighbor)
- [ ] Surface topology assessed (concave/convex/flat)
- [ ] Design tool chosen based on topology and interface size
- [ ] Hotspots formatted as chain + label_seq_id for tool input
