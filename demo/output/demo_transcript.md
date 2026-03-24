# BY Demo Transcript — VHH Nanobody Design Against RBX1

Run started: 2026-03-24T19:09:25.554Z

## Prompt

> Design VHH nanobodies against RBX1. Use standard campaign tier. Present results as a ranked table with ipSAE, ipTM, pLDDT, and liability columns. Include a diversity analysis of the top candidates.

## Conversation

### BY Agent

Using the **proteus-design-workflow** skill to orchestrate this nanobody campaign against RBX1.

### BY Agent

I'll orchestrate a full nanobody design campaign against RBX1. Let me start with **Stage 1: Target Preparation** — fetching structural and sequence data in parallel.

### BY Agent



Starting parallel target research — PDB structures, UniProt data, and known antibody binders:

### BY Agent

Good data. RBX1 is a small 108-residue RING domain protein (P62877), no known antibodies in SAbDab — this is a **novel target**. Let me inspect the best structures to pick the right one for design.

### BY Agent

Excellent data. **3DPL** is the best structure: 2.6Å X-ray, RBX1 chain R (106 residues) complexed with Cullin-5 chain C. No known antibodies in SAbDab — this is a **first-in-class** target.

### BY Agent

Target analysis complete. Here's the situation:

**RBX1 (P62877)** — 108-residue RING domain E3 ligase component
- Best structure: **3DPL** (2.6Å X-ray, chain R = RBX1, chain C = Cullin-5)
- Cullin-5 interface occupies N-terminal region (residues 20-39) and C-terminal tail (102-108)
- Zinc-binding RING domain residues: 42, 45, 53, 56, 68, 75, 77, 80, 82, 83, 94, 97
- **No known antibodies** in SAbDab — first-in-class target

**Stage 2: Epitope Selection** — I'll target the exposed RING domain surface (residues 86-101) that includes the E2-binding region, avoiding both the Cullin interface and zinc-coordinating residues:

| Residue | Type | Rationale |
|---------|------|-----------|
| R86 | Charged (Arg) | Surface-exposed, E2-proximal |
| W87 | Aromatic (Trp) | Large contact surface |
| K89 | Charged (Lys) | Surface-exposed loop |
| R91 | Charged (Arg) | Spatially clustered with R86 |
| R99 | Charged (Arg) | C-terminal exposed region |
| W101 | Aromatic (Trp) | Strong VHH contact potential |

Now invoking the **BoltzGen** skill for the exact entities YAML format.

### BY Agent

Good — I have the full BoltzGen spec. Now I need to determine the compute path. Let me check local GPU availability and fetch Tamarind tools in parallel.

### BY Agent

Excellent setup:
- **NVIDIA RTX PRO 6000 Blackwell** — 97 GB VRAM (43 GB free)
- **BoltzGen installed** at `/data/proteus/proteus-design`
- **Protenix installed** at `/data/proteus/Protenix`
- **3DPL.cif downloaded** to `/tmp/rbx1_campaign/`

Local GPU is the fastest path. Let me fetch the local BoltzGen runner and set up the campaign.

### BY Agent



Now let me create the campaign and write the entities YAML spec. The epitope residues in 3DPL chain R `label_seq_id` are: **84, 85, 87, 89, 97, 99** (mapped from UniProt 86, 87, 89, 91, 99, 101).

### BY Agent

Campaign created: **rbx1-20260324-191309**. Now writing the entities YAML and getting a cost estimate.

### BY Agent

**Cost estimate** (full standard tier): ~$6,050 total if taken to lab. But we're running locally on your RTX PRO 6000, so **compute cost = $0** — just GPU time. Lab costs only apply if you later approve Adaptyv Bio submission.

**Campaign sizing**: 30 designs, nanobody-anything protocol, budget 96 diffusion steps (production quality). ~1.5 hours estimated on your GPU.

### BY Agent

Launching BoltzGen on your local RTX PRO 6000 Blackwell (43 GB free). This will take a while — running in background.

### BY Agent

CLI not on PATH. Let me find the actual binary and try the direct approach.

### BY Agent

The `proteus-ab` binary is in a local venv. Let me run it directly through the venv activation.

### BY Agent

Local venv not set up. Let me switch to **Tamarind Bio** (the default provider) — it handles everything cloud-side.

### BY Agent

Found the BoltzGen schema on Tamarind. I need to upload the target file first, then submit. Let me fetch the upload tool.

### BY Agent

CIF upload might not have worked — Tamarind expects PDB format. Let me download in PDB format and re-upload.

## Timing

| Phase | Duration |
|-------|----------|
| research | 224.1s |
| planning | 43.7s |
| design | 106.9s |
| research | 0.1s |
| **Total** | **375.5s** |

Run completed: 2026-03-24T19:15:41.083Z