const TOOL_MAP: Record<string, string> = {
  // PDB
  pdb_search: "Searching PDB",
  pdb_fetch_structure: "Fetching structure",
  pdb_get_chains: "Analyzing chains",
  pdb_interface_residues: "Analyzing interface",
  pdb_download: "Downloading structure",

  // UniProt
  uniprot_search: "Searching UniProt",
  uniprot_fetch_protein: "Fetching protein data",
  uniprot_get_domains: "Fetching domain info",
  uniprot_get_variants: "Fetching variants",

  // SAbDab
  sabdab_search_by_antigen: "Searching antibody database",
  sabdab_search: "Searching SAbDab",

  // Research
  research_search_prior_art: "Searching literature",
  research_get_target_info: "Researching target",
  research_analyze_known_binders: "Analyzing known binders",
  research_find_similar_targets: "Finding similar targets",
  research_check_novelty: "Checking novelty",

  // Tamarind
  tamarind_list_tools: "Listing cloud tools",
  tamarind_list_models: "Listing models",
  tamarind_upload_file: "Uploading file",
  tamarind_submit_job: "Submitting to Tamarind",
  tamarind_submit_batch: "Submitting batch job",
  tamarind_get_job: "Checking job status",
  tamarind_get_job_status: "Checking job status",
  tamarind_get_job_results: "Downloading results",
  tamarind_wait_for_job: "Waiting for job",
  tamarind_screen_developability: "Screening developability",
  tamarind_screen_naturalness: "Scoring naturalness",

  // Levitate
  levitate_list_pipelines: "Listing pipelines",
  levitate_run_rfantibody: "Running RFAntibody",
  levitate_run_analysis: "Running analysis",
  levitate_get_results: "Downloading results",
  levitate_estimate_cost: "Estimating cost",

  // Screening
  screen_liabilities: "Scanning liabilities",
  screen_developability: "Assessing developability",
  screen_composite: "Running composite screen",
  screen_net_charge: "Computing net charge",
  score_ipsae: "Computing ipSAE",
  interpret_scores: "Interpreting scores",
  screen_diversity: "Analyzing diversity",
  screen_diagnose_failures: "Diagnosing failures",
  screen_pareto_front: "Computing Pareto front",
  screen_align_sequences: "Aligning sequences",
  screen_naturalness: "Scoring naturalness",
  screen_cross_validate: "Cross-validating",

  // Campaign
  campaign_create: "Creating campaign",
  campaign_get: "Loading campaign",
  campaign_get_summary: "Loading campaign summary",
  campaign_update_status: "Updating status",
  campaign_add_round: "Adding round",
  campaign_update_round: "Updating round",
  campaign_record_scores: "Recording scores",
  campaign_get_cost_estimate: "Estimating campaign cost",
  campaign_suggest_next_round: "Optimizing parameters",
  campaign_export_fasta: "Exporting FASTA",
  campaign_export_csv: "Exporting CSV",
  campaign_generate_visualization: "Generating PyMOL script",

  // Knowledge
  knowledge_add_entity: "Updating knowledge graph",
  knowledge_query: "Querying knowledge",

  // Adaptyv Bio (lab integration)
  adaptyv_prepare_submission: "Preparing lab submission",
  adaptyv_confirm_submission: "Confirming submission",
  adaptyv_estimate_cost: "Estimating lab cost",
  adaptyv_get_experiment_status: "Checking experiment",
  adaptyv_get_results: "Downloading lab results",

  // Local compute
  local_run_boltzgen: "Running BoltzGen locally",
  local_run_pxdesign: "Running PXDesign locally",
  local_run_protenix: "Running Protenix locally",
  ssh_run_job: "Running remote job",
};

// Infrastructure tools to HIDE from user
const HIDDEN_TOOLS = new Set([
  "Read",
  "Write",
  "Edit",
  "Bash",
  "Glob",
  "Grep",
  "WebFetch",
  "WebSearch",
  "Agent",
  "Task",
  "TaskCreate",
  "TaskUpdate",
  "TodoWrite",
  "NotebookEdit",
  "SendMessage",
  "ToolSearch",
]);

export function humanizeToolName(name: string): string {
  // Strip MCP prefix (mcp__proteus_pdb__pdb_search -> pdb_search)
  const stripped = name.replace(/^mcp__[^_]+__/, "");
  return TOOL_MAP[stripped] || stripped.replace(/_/g, " ");
}

export function shouldShowTool(name: string): boolean {
  const stripped = name.replace(/^mcp__[^_]+__/, "");
  return !HIDDEN_TOOLS.has(name) && !HIDDEN_TOOLS.has(stripped);
}

export function getToolCategory(name: string): string {
  const stripped = name.replace(/^mcp__[^_]+__/, "");
  if (stripped.startsWith("pdb_")) return "PDB";
  if (stripped.startsWith("uniprot_")) return "UniProt";
  if (stripped.startsWith("sabdab_")) return "SAbDab";
  if (stripped.startsWith("research_")) return "Research";
  if (stripped.startsWith("tamarind_")) return "Tamarind";
  if (stripped.startsWith("levitate_")) return "Levitate";
  if (stripped.startsWith("screen_") || stripped.startsWith("score_"))
    return "Screening";
  if (stripped.startsWith("campaign_")) return "Campaign";
  if (stripped.startsWith("knowledge_")) return "Knowledge";
  if (stripped.startsWith("adaptyv_")) return "Adaptyv";
  if (stripped.startsWith("local_") || stripped.startsWith("ssh_"))
    return "Compute";
  return "Other";
}
