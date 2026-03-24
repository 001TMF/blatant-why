<p align="center">
  <img src="assets/banner.png" alt="Blatant-Why" width="700">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://github.com/001TMF/blatant-why/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
</p>

An autonomous antibody design agent that connects the Anthropic API, BoltzGen, Tamarind Bio, and Adaptyv Bio into a single pipeline. Give it a target. Get lab-ready nanobody candidates. No platform fee.

---

<p align="center">
  <img src="assets/time_comparison.png" alt="Time comparison: traditional vs. agentic antibody design" width="500">
</p>
<p align="center"><sub>Source: trust us bro</sub></p>
<p align="center"><sub>(Interactive version: <a href="assets/blatant_why_time_parody_v4.html">assets/blatant_why_time_parody_v4.html</a>)</sub></p>

---

## Why?

Because this morning we watched a $50M company announce an "autonomous AI agent for drug design" that wraps open-source structure prediction models in an LLM agent and calls it a breakthrough.

When your "proprietary scoring engine" is open-source structure prediction with a wrapper, and your "autonomous design platform" is an LLM calling APIs that anyone can call -- maybe the revolution isn't what you're selling.

We think the antibody discovery community deserves to know: **the agentic orchestration layer is not the hard part.** The models are open. The APIs are available. A good engineer can wire this together in a week.

So we did. And we're giving it away.

---

## Quick Start

```bash
npx by-design init
claude
> "Design VHH nanobodies against PD-L1"
```

That's it. `by-design init` generates everything Claude Code needs -- MCP servers, agents, skills, commands, hooks, and a CLAUDE.md personality file. Open Claude Code in the same directory and you have a protein design workstation.

**Prerequisites:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [uv](https://docs.astral.sh/uv/), Python >= 3.11, Node.js >= 18.

---

## What's Inside

- **10 MCP servers** -- PDB, UniProt, SAbDab, screening, cloud compute, knowledge, campaign, research, Adaptyv Bio, local compute
- **12 agents** -- research, design, screening, evaluation, visualization, diversity, campaign, knowledge, verifier, plan-checker, environment, lab
- **15 skills** -- BoltzGen, Protenix, PXDesign, scoring, screening, epitope analysis, campaign management, and more
- **8 slash commands** -- `/by:load`, `/by:screen`, `/by:results`, `/by:watch`, `/by:status`, `/by:approve-lab`, `/by:set-profile`, `/by:setup`
- **ChromaDB learning system** -- semantic memory that improves with every campaign
- **Tamarind Bio cloud compute** -- free tier, 200+ structural biology models, no GPU required

---

## The Actual Hard Problems

Blatant-Why is a wrapper. We know it's a wrapper. That's the point.

Here's what it doesn't solve -- and what the team behind it ([Lyceum](https://lyceum.bio) / [Phytovenomics](https://phytovenomics.com)) is actually working on:

- **Proprietary scoring models** that go beyond open-source structure prediction -- trained on experimental binding data that doesn't exist in the PDB
- **Closing the wet lab loop** with real experimental validation, not just computational confidence scores
- **Generating training datasets** from high-throughput screening that feed back into better models

Blatant-Why is our way of saying: **stop paying for wrappers. Start asking what's underneath.**

---

## Credits

- [Hannes Stark](https://github.com/jostorge/boltzgen) and the MIT team for BoltzGen
- [Deniz Kavi](https://tamarind.bio) and Sherry Liu at Tamarind Bio
- [Julian Englert](https://www.adaptyvbio.com) at Adaptyv Bio
- The [Anthropic Claude](https://docs.anthropic.com/en/docs/claude-code) team

---

## License

[MIT](LICENSE)

---

Full technical documentation: [docs/](docs/)
