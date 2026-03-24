# SARS-CoV-2 RBD VHH Nanobody Design Campaign - Master Plan

## Executive Summary

### Campaign Objectives
**Primary Goal**: Design and synthesize 10-15 high-affinity VHH nanobodies targeting SARS-CoV-2 RBD with broad variant coverage and therapeutic potential.

**Success Metrics**:
- Primary endpoint: 3-5 high-affinity VHH candidates (KD < 10 nM)
- Secondary endpoints: Broad variant neutralization (Alpha, Beta, Gamma, Delta, Omicron), excellent developability scores
- Safety gate: Triple-layer approval for lab synthesis (automated + orchestrator + manual)

### Resource Requirements
- **Timeline**: 4 weeks total (1 week computational, 3 weeks lab synthesis)
- **Budget**: $3,517 USD (Tamarind Bio + Adaptyv standard) or $5,517 USD (premium package)
- **Personnel**: Campaign orchestrator + automated agent teams
- **Compute**: Tamarind Bio free tier (recommended) with Levitate Bio backup

### Expected Deliverables
1. 10-15 validated VHH sequences with comprehensive scoring
2. Structural models and binding interface analysis
3. Detailed screening reports and visualization scripts
4. Lab-ready constructs with expression optimization
5. Comprehensive campaign audit trail and decision logs

---

## Phase-by-Phase Workflow

### Phase 1: Target Research and Analysis ✅ COMPLETED
**Duration**: Day 0 (completed)
**Status**: Comprehensive analysis delivered

**Key Outputs**:
- SARS-CoV-2 RBD structural analysis with 5 high-resolution templates (PDB: 8Q7S, 8Q95, 8Q94, 7Q3Q, 7OLZ)
- Epitope landscape mapping with conserved vs. variable regions
- Variant analysis covering Alpha through Omicron lineages
- VHH precedent analysis with successful design patterns
- Identified target zones: Framework regions (>95% conservation), allosteric sites, quaternary epitopes

### Phase 2: Design Generation
**Duration**: Days 1-3
**Agent Team**: Design Agent + Monitor
**MCP Servers**: tamarind, screening, campaign

**Round 1 - Broad Exploration**:
- **Target**: 800 designs across 8 VHH scaffolds (100 designs per scaffold)
- **Scaffolds**: High-performing RBD-binding VHH frameworks from PDB analysis
- **Parameters**:
  - CDR3 length: 12-20 residues (VHH optimal range)
  - Target epitopes: Conserved framework regions (Tier 1 priority)
  - Diversity sampling: Maximum scaffold variety
- **Compute Provider**: Tamarind Bio (free tier, 200+ model credits)
- **Expected Output**: ~800 raw designs → ~300-400 after structure prediction

**Round 2 - Focused Refinement**:
- **Target**: 250 designs across 5 best scaffolds (50 designs per scaffold)
- **Focus**: Optimization of promising hits from Round 1
- **Parameters**:
  - Refined CDR engineering based on Round 1 insights
  - Allosteric site targeting (Tier 2 priority)
  - Enhanced affinity maturation
- **Expected Output**: ~250 designs → ~100-150 after screening

### Phase 3: Screening and Ranking
**Duration**: Days 4-5
**Agent Team**: Screening Agent
**MCP Servers**: screening, campaign

**Stage 1 - Structure Prediction Screening**:
- **Metrics**: ipTM ≥ 0.5, ipSAE ≥ 0.3, pLDDT ≥ 70, RMSD ≤ 3.5 Å
- **Tools**: `screen_composite`, `interpret_scores`
- **Expected**: ~300-400 → ~150-200 designs

**Stage 2 - Developability Screening**:
- **Liability Analysis**: Deamidation (≤6 total), Aspartate isomerization (≤3), Met/Trp oxidation (≤6), free cysteines (0)
- **Physicochemical**: Hydrophobic fraction ≤0.45, net charge -5 to +10, CDR length ≤50 residues
- **Tools**: `screen_liabilities`, `screen_developability`, `screen_net_charge`
- **Expected**: ~150-200 → ~75-100 designs

**Stage 3 - Binding Interface Analysis**:
- **Interface Quality**: ≥15 contacts, contact density ≥0.8, interface size 12-25 residues
- **RBD-Specific**: ≥3 hotspot residues, ACE2 competition analysis
- **Tools**: `screen_shape_complementarity`, structure analysis
- **Expected**: ~75-100 → ~30-50 designs

**Stage 4 - Diversity and Naturalness**:
- **Diversity**: ≤90% pairwise identity, CDR3 diversity ≤85%, diversity ratio ≥0.5
- **Naturalness**: AbLang2 score ≥-4.0 (if available), framework identity ≥95%
- **Tools**: `screen_diversity`, `screen_align_sequences`, `screen_naturalness`
- **Expected**: ~30-50 → ~15-25 designs

**Final Ranking**:
- **Composite Scoring**: Weighted formula (30% ipSAE, 25% ipTM, 20% liability penalty, 15% pLDDT, 10% interface quality)
- **Pareto Optimization**: Multi-objective optimization for binding vs. developability
- **Tools**: `screen_pareto_front`, custom scoring pipeline
- **Output**: Top 15 candidates for lab synthesis

### Phase 4: Lab Synthesis (TRIPLE-GATED)
**Duration**: Days 8-28 (3 weeks)
**Lab Partner**: Adaptyv Bio
**Safety Protocol**: Layer 1 (MCP confirmation) + Layer 2 (orchestrator check) + Layer 3 (manual approval)

**Gene Synthesis & Cloning** (Week 1):
- 15 sequences synthesized with codon optimization
- Expression vector cloning (likely pET-based for E. coli)
- Quality control sequencing verification

**Expression Optimization** (Week 2):
- Small-scale expression testing in E. coli
- Solubility and yield optimization
- Purification protocol development

**Production & QC** (Week 3):
- Scale-up production of successful constructs
- Protein purification and characterization
- Quality control: SDS-PAGE, mass spec, preliminary binding assays
- Final candidate delivery with documentation

---

## Technical Specifications

### VHH Design Parameters

**Framework Selection**:
- **Primary Scaffolds**: Derived from successful RBD-binding VHHs (Re32D03, Ma6F06, VHH-12)
- **Framework Requirements**: >95% germline identity for immunogenicity minimization
- **Disulfide Pattern**: 2 canonical + 0-1 additional for VHH stability

**CDR Engineering Guidelines**:
- **CDR1/2**: Maintain framework interactions, limited modifications for stability
- **CDR3**: Primary engineering target, 12-20 residues optimal for VHHs
- **Binding Target**: KD < 10 nM for competitive neutralization
- **Specificity**: Target conserved epitopes outside ACE2 binding site for variant resistance

**Target Epitope Strategy**:
1. **Tier 1**: Framework regions with >95% variant conservation
2. **Tier 2**: Allosteric sites distant from ACE2 interface
3. **Tier 3**: Quaternary epitopes spanning multiple RBD units

### Computational Pipeline

**Design Generation**:
- **Primary**: BoltzGen via Tamarind Bio (antibody-specific models)
- **Backup**: Levitate Bio RFAntibody pipeline
- **Local**: Local GPU setup if cloud providers unavailable

**Structure Prediction**:
- **Primary**: Protenix via Tamarind Bio for complex prediction
- **Validation**: Cross-validation with AlphaFold3 where possible
- **Confidence**: Multiple seed sampling for robust predictions

**Screening Tools**:
- **Structure**: ipTM/ipSAE/pLDDT scoring via MCP screening server
- **Developability**: Comprehensive liability and physicochemical analysis
- **Interface**: Shape complementarity and contact analysis
- **Diversity**: Sequence clustering and naturalness assessment

### Quality Control Checkpoints

**Automated QC Gates**:
1. Structure validation (atom completeness, geometry checks)
2. Sequence validation (VHH framework, disulfide connectivity)
3. Cross-validation (multiple predictor consensus)
4. Liability screening (PTM risk assessment)

**Manual Review Triggers**:
- ipSAE > 0.6 with unusual CDR3 composition
- High liability count with excellent binding scores
- Novel CDR conformations outside training data
- Extreme physicochemical properties

---

## Risk Management

### Technical Risks and Mitigation

**Risk 1: Low Hit Rate (<20% pass screening)**
- **Probability**: Medium
- **Impact**: High (campaign failure)
- **Mitigation**:
  - Diverse scaffold library with 8 different frameworks
  - Conservative epitope targeting strategy
  - Backup round with 500-1000 additional designs (+$8-15)
- **Detection**: Use `screen_diagnose_failures` for bottleneck analysis

**Risk 2: Poor Binding Predictions**
- **Probability**: Low-Medium
- **Impact**: High
- **Mitigation**:
  - Multiple structure prediction tools for validation
  - Conservative ipSAE/ipTM thresholds (0.3/0.5)
  - Target well-validated epitopes from PDB analysis
- **Detection**: Systematic under-performance in Stage 1 screening

**Risk 3: Expression/Solubility Failures (>30%)**
- **Probability**: Medium
- **Impact**: Medium
- **Mitigation**:
  - Comprehensive developability screening (Stage 2)
  - Adaptyv Bio expression optimization service
  - Conservative physicochemical property thresholds
- **Contingency**: Additional synthesis round (+$1,000-1,500)

**Risk 4: Variant Escape Mutations**
- **Probability**: Medium-High (future variants)
- **Impact**: Medium
- **Mitigation**:
  - Target framework regions with >95% conservation
  - Avoid ACE2 binding site hotspots
  - Design for known escape mutations proactively
- **Detection**: Poor neutralization against variant panel

### Cost Overrun Scenarios

**Scenario 1: Additional Design Round Required**
- **Trigger**: <5 candidates pass screening
- **Cost Impact**: +$8-15 computational, +$1,000-2,000 lab
- **Contingency**: Levitate Bio backup provider ready

**Scenario 2: Enhanced Lab Package Required**
- **Trigger**: >30% expression failures
- **Cost Impact**: +$2,000 (standard → premium package)
- **Benefit**: Higher success rate, additional purification

**Scenario 3: Validation Round Required**
- **Trigger**: Poor binding validation results
- **Cost Impact**: +$500-1,000 computational, +$2,000-3,000 lab
- **Timeline**: Additional 2-3 weeks

### Timeline Dependencies and Critical Path

**Critical Path**: Design Generation → Screening → Lab Synthesis
- **Dependency 1**: Tamarind Bio availability (backup: Levitate Bio)
- **Dependency 2**: Adaptyv Bio capacity (3-week lead time)
- **Dependency 3**: Manual lab approval process (potential delay)

**Risk Mitigation**:
- Multiple compute provider accounts pre-configured
- Early lab partner engagement and slot reservation
- Parallel processing where possible (design rounds, screening stages)

---

## Resource Allocation

### Compute Provider Selection and Rationale

**Primary Choice: Tamarind Bio**
- **Cost**: $16.67 for full campaign (exceptionally cost-effective)
- **Advantages**: Free tier, 200+ model credits, no infrastructure required
- **Capabilities**: BoltzGen + Protenix pipeline, nanobody-specific models
- **Risk**: Provider availability, quota limitations

**Secondary Choice: Levitate Bio**
- **Cost**: $532-910 with academic discount
- **Advantages**: RFAntibody specialization, integrated pipeline, high success rate
- **Use Case**: Backup if Tamarind unavailable, premium accuracy requirements

**Tertiary Choice: Local GPU**
- **Setup Cost**: $2,000-2,500 (one-time)
- **Ongoing**: $364 per campaign
- **Advantages**: Full control, unlimited designs, no data transfer
- **Use Case**: High-volume campaigns, data security requirements

### Budget Breakdown with Alternatives

**Standard Package (Recommended): $3,517 Total**
```
Computational (Tamarind Bio):     $17    (0.5%)
Lab Synthesis (Adaptyv Standard): $3,500 (99.5%)
```

**Premium Package: $5,517 Total**
```
Computational (Tamarind Bio):     $17    (0.3%)
Lab Synthesis (Adaptyv Premium):  $5,500 (99.7%)
```

**Academic/High-Volume: $4,032-4,410 Total**
```
Computational (Levitate Bio):     $532-910  (13-21%)
Lab Synthesis (Adaptyv Standard): $3,500    (79-87%)
```

### Personnel Requirements and Responsibilities

**Campaign Orchestrator** (Primary Role):
- Overall campaign planning and execution
- Agent team deployment and coordination
- Git workflow management and code review
- Safety gate enforcement and decision logging
- Final candidate selection and lab approval

**Research Agent Team**:
- Target analysis and structural database queries ✅ COMPLETED
- Literature review and precedent analysis ✅ COMPLETED
- Epitope mapping and conservation analysis ✅ COMPLETED

**Design Agent Team**:
- Scaffold selection and parameter optimization
- Design generation via cloud providers
- Structure prediction and initial filtering
- Performance monitoring and optimization

**Screening Agent Team**:
- Multi-stage screening pipeline execution
- Liability and developability assessment
- Interface analysis and binding prediction
- Diversity analysis and final ranking

**Lab Integration (GATED)**:
- Adaptyv Bio submission preparation
- Triple-layer safety gate enforcement
- Progress monitoring and quality control
- Results integration and analysis

---

## Success Criteria

### Primary Endpoint
**Target**: 3-5 high-affinity VHH candidates with KD < 10 nM
- **Measurement**: Surface plasmon resonance (SPR) or biolayer interferometry (BLI)
- **Timeline**: Week 4 deliverable
- **Success Threshold**: ≥3 candidates meeting affinity target

### Secondary Endpoints

**Broad Variant Neutralization**:
- **Target**: Neutralization of Alpha, Beta, Gamma, Delta, Omicron variants
- **Measurement**: Pseudovirus neutralization assays
- **Success**: ≥50% of candidates show broad neutralization (IC50 < 100 nM)

**Excellent Developability Scores**:
- **Structure Quality**: ipTM ≥ 0.6, pLDDT ≥ 75, ipSAE ≥ 0.4
- **Liability Assessment**: ≤3 medium-severity PTM liabilities
- **Physicochemical**: Within drug-like property ranges
- **Success**: ≥80% of final candidates meet all criteria

**Expression and Solubility**:
- **Expression**: >10 mg/L in standard E. coli systems
- **Solubility**: >90% soluble fraction at 1 mg/mL
- **Stability**: Tm > 60°C for therapeutic viability
- **Success**: ≥70% of candidates meet expression criteria

### Safety Gates and Go/No-Go Decisions

**Go/No-Go Gate 1 (Day 3)**: Design Generation
- **Criteria**: ≥500 total designs generated across both rounds
- **Go**: Proceed to screening with full pipeline
- **No-Go**: Deploy additional design round or switch providers

**Go/No-Go Gate 2 (Day 5)**: Screening Completion
- **Criteria**: ≥10 candidates pass all screening stages
- **Go**: Proceed to lab synthesis with top 15 candidates
- **No-Go**: Reduce stringency or generate additional designs

**SAFETY GATE 3 (Day 7)**: Lab Synthesis Approval
- **Layer 1**: MCP tool confirmation code (5-minute TTL)
- **Layer 2**: Orchestrator verification of campaignState.labApproved
- **Layer 3**: Manual TUI approval file (/approve-lab command)
- **Requirement**: ALL three layers must confirm before Adaptyv submission
- **No Bypass**: Safety gates cannot be overridden, even with elevated permissions

### Campaign Success Classifications

**Minimum Success**:
- ≥5 candidates meet all screening criteria
- ≥2 candidates with predicted high affinity (ipSAE > 0.5)
- Successful completion within budget and timeline

**Good Success**:
- ≥10 candidates with composite score ≥0.7
- ≥3 distinct epitope targets represented
- High diversity in final candidate set (≥8 unique clusters)

**Exceptional Success**:
- ≥15 high-quality candidates spanning multiple epitopes
- Novel binding modes or epitopes discovered
- Pipeline optimizations identified for future campaigns
- All lab synthesis candidates express successfully

---

## Implementation Timeline

### Week 1: Computational Design and Screening

**Day 1**: Campaign Setup and Design Generation
- Morning: Campaign initialization, agent team deployment
- Afternoon: Round 1 design generation (800 designs, 8 scaffolds)
- Evening: Initial structure prediction and filtering

**Day 2**: Continued Design and Round 2
- Morning: Round 1 completion and analysis
- Afternoon: Round 2 design generation (250 designs, 5 scaffolds)
- Evening: Combined structure prediction screening

**Day 3**: Primary Screening (Stages 1-2)
- Morning: Structure prediction screening (Stage 1)
- Afternoon: Developability screening (Stage 2)
- Evening: Go/No-Go Gate 1 assessment

**Day 4**: Advanced Screening (Stages 3-4)
- Morning: Binding interface analysis (Stage 3)
- Afternoon: Diversity and naturalness screening (Stage 4)
- Evening: Composite scoring and ranking

**Day 5**: Final Selection and Lab Prep
- Morning: Pareto optimization and final candidate selection
- Afternoon: Documentation and visualization generation
- Evening: Go/No-Go Gate 2, lab submission preparation

**Days 6-7**: Safety Gate and Submission
- Review period: Manual candidate review and validation
- Safety Gate 3: Triple-layer lab approval process
- Submission: Adaptyv Bio order placement and documentation

### Weeks 2-4: Lab Synthesis and Validation

**Week 2**: Gene Synthesis and Cloning
- Days 8-10: Gene synthesis with codon optimization
- Days 11-12: Vector cloning and transformation
- Days 13-14: Sequencing verification and quality control

**Week 3**: Expression Optimization
- Days 15-17: Small-scale expression testing
- Days 18-19: Solubility and purification optimization
- Days 20-21: Protocol development and scaling preparation

**Week 4**: Production and Delivery
- Days 22-24: Large-scale expression and purification
- Days 25-26: Final quality control and characterization
- Days 27-28: Documentation, packaging, and delivery

---

## Conclusion

This comprehensive campaign plan integrates extensive SARS-CoV-2 RBD research, cost-effective computational design strategies, and rigorous screening protocols to deliver 10-15 high-quality VHH nanobody candidates within 4 weeks at $3,517-5,517 USD.

The multi-phase approach balances broad design exploration with focused optimization, while layered safety gates ensure responsible lab integration. Success criteria are clearly defined with multiple fallback strategies to mitigate technical and cost risks.

The campaign represents exceptional value compared to traditional antibody development approaches (3-7x cost reduction, 4-12x time reduction) while leveraging state-of-the-art computational tools and established lab partnerships.

**Expected Outcome**: 3-5 high-affinity, broad-spectrum VHH candidates ready for advanced therapeutic development.

---

*Campaign Plan Version 1.0 - Generated March 24, 2026*
*Integration of: SARS-CoV-2 RBD Analysis + Cost Analysis + Screening Gates*
*Ready for campaign execution via Proteus orchestrator*