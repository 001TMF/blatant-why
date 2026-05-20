# Config & Environment Schema

This document defines the canonical schemas for `.by/config.json` and
`.by/environment.json`. The `by-session` skill writes both. Downstream skills
(`by-design-workflow`, `by-screening`, design engines) read them.

The schemas below are JSON-Schema-style descriptions, not literal JSON Schema files,
because we ship them as prose for human review. `scripts/validate_config.py`
implements the validation rules below.

---

## 1. `.by/config.json` — User Preferences

**Purpose:** Captures the user's *choices* — compute provider, model profile,
campaign defaults, safety toggles. This file is canonical. Every BY skill that
needs to know "which compute provider should I use?" reads this file.

**Lifecycle:** Created by `init_questionnaire.py` on first session start. Updated
by slash commands (`/by:set-profile`, `/by:setup`) and by direct user requests
("switch to Tamarind"). Never overwritten wholesale — always read-modify-write.

### Top-level shape

```json
{
  "model_profile": "balanced",
  "compute": { ... },
  "workflow": { ... },
  "safety": { ... }
}
```

| Field | Type | Required | Allowed values | Default |
|-------|------|----------|----------------|---------|
| `model_profile` | string | yes | `quality` \| `balanced` \| `budget` | `balanced` |
| `compute` | object | yes | (see § 1.1) | (see § 1.1) |
| `workflow` | object | yes | (see § 1.2) | (see § 1.2) |
| `safety` | object | yes | (see § 1.3) | (see § 1.3) |

### 1.1 `compute` block

```json
{
  "compute": {
    "default_provider": "local",
    "providers_priority": ["local", "hpc", "tamarind"],
    "fallback_allowed": false,
    "local_gpu": true,
    "local": {
      "boltzgen":  {"path": null, "conda_env": "bg",        "weights": false},
      "protenix":  {"path": null, "conda_env": "protenix",  "weights": false},
      "pxdesign":  {"path": null, "conda_env": "pxdesign",  "weights": false}
    },
    "hpc": {
      "target": "runpod",
      "endpoint_url": null,
      "api_key_env": "RUNPOD_API_KEY"
    },
    "tamarind": {
      "tier": "free",
      "api_key_env": "TAMARIND_API_KEY"
    },
    "ssh_hosts": []
  }
}
```

| Field | Type | Required | Allowed values | Default |
|-------|------|----------|----------------|---------|
| `default_provider` | string | yes | `local` \| `hpc` \| `tamarind` \| `auto` | **`local`** |
| `providers_priority` | string[] | yes | ordered subset of `[local, hpc, tamarind]` | **`["local", "hpc", "tamarind"]`** |
| `fallback_allowed` | boolean | no | true / false | `false` |
| `local_gpu` | boolean | no | true / false | `true` |
| `local.<tool>.path` | string \| null | no | absolute filesystem path | `null` until detected |
| `local.<tool>.conda_env` | string | no | conda env name | per-tool default |
| `local.<tool>.weights` | boolean | no | true / false | `false` until verified |
| `hpc.target` | string | yes if `default_provider == "hpc"` | `runpod` \| `modal` \| `lambda` \| `local_hpc` | `runpod` |
| `hpc.endpoint_url` | string \| null | no | URL | `null` |
| `hpc.api_key_env` | string | yes if `default_provider == "hpc"` | env var name (e.g., `RUNPOD_API_KEY`) | `RUNPOD_API_KEY` |
| `tamarind.tier` | string | no | `free` \| `pro` | `free` |
| `tamarind.api_key_env` | string | no | env var name | `TAMARIND_API_KEY` |
| `ssh_hosts` | object[] | no | per-host blocks (see § 1.4) | `[]` |

**Validation rules (enforced by `validate_config.py`):**

1. `default_provider` must be one of `local`, `hpc`, `tamarind`, `auto`.
2. `providers_priority` must be a non-empty list of provider names from the
   allowed set; no duplicates; `local` should appear first in the default install.
3. If `default_provider == "hpc"`, then `hpc.target` and `hpc.api_key_env` MUST be
   non-empty.
4. If `default_provider == "tamarind"`, then `tamarind.api_key_env` MUST be
   non-empty. The skill does NOT require the env var itself to be set at config
   write time — but it should warn if missing.
5. If `default_provider == "local"`, the `local.<tool>` blocks may have `path:
   null` initially; `/by:setup` later fills them in. The session skill should
   surface unset paths as `✗ not configured` but not block.
6. `fallback_allowed: false` means downstream skills MUST NOT silently switch
   providers. This is the safe default. If `true`, downstream skills may
   transparently failover in `providers_priority` order.

### 1.2 `workflow` block

```json
{
  "workflow": {
    "auto_research": true,
    "auto_screen": true,
    "fold_validation": true,
    "default_campaign_tier": "standard"
  }
}
```

| Field | Type | Required | Allowed values | Default |
|-------|------|----------|----------------|---------|
| `auto_research` | boolean | no | true / false | `true` |
| `auto_screen` | boolean | no | true / false | `true` |
| `fold_validation` | boolean | no | true / false | `true` |
| `default_campaign_tier` | string | no | `preview` \| `standard` \| `production` | `standard` |

### 1.3 `safety` block

```json
{
  "safety": {
    "require_plan_approval": true,
    "require_lab_approval": true
  }
}
```

| Field | Type | Required | Default | Meaning |
|-------|------|----------|---------|---------|
| `require_plan_approval` | boolean | no | `true` | Block compute submission until plan is approved |
| `require_lab_approval` | boolean | no | `true` | Block Adaptyv lab submission unless triple-gated |

Both default to `true` and should rarely be flipped. If they're flipped to
`false`, the validator emits a WARNING (not an error).

### 1.4 `ssh_hosts` block (optional, advanced)

For users with a private HPC cluster reachable via SSH:

```json
{
  "ssh_hosts": [
    {
      "name": "lab-gpu-01",
      "host": "gpu01.example.edu",
      "user": "tristan",
      "key_path": "~/.ssh/id_ed25519",
      "gpu_type": "A100-80GB"
    }
  ]
}
```

This is informational only — actual deployment is done via `by-deploy-compute`.

---

## 2. `.by/environment.json` — Auto-Detected Snapshot

**Purpose:** What the discovery script (`/by:setup`) found on the host. Distinct
from `config.json` (which is *user choice*), this file is *facts on the ground*.
If the two disagree, `config.json` wins.

**Lifecycle:** Written by `/by:setup`. Read by `by-session` at session start for
the status display. Stale after 24h — the session skill should suggest a refresh
if `last_scanned_at` is older.

### Top-level shape

```json
{
  "schema_version": "1.0",
  "last_scanned_at": "2026-05-20T14:32:11Z",
  "host": { ... },
  "gpu": { ... },
  "local_tools": { ... },
  "providers_detected": { ... }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema_version` | string | yes | `1.0` |
| `last_scanned_at` | string (ISO 8601) | yes | UTC timestamp of last `/by:setup` |
| `host` | object | yes | OS, arch, hostname |
| `gpu` | object | no | Absent if no NVIDIA GPU detected |
| `local_tools` | object | yes | Per-tool detection results |
| `providers_detected` | object | yes | What providers are usable on this host |

### 2.1 `host`

```json
{
  "host": {
    "os": "Linux",
    "kernel": "6.5.0-generic",
    "arch": "x86_64",
    "hostname": "lab-workstation-1",
    "python_version": "3.11.6",
    "conda_version": "24.1.2"
  }
}
```

### 2.2 `gpu`

```json
{
  "gpu": {
    "count": 1,
    "devices": [
      {"index": 0, "name": "NVIDIA RTX PRO 6000", "vram_gb": 96, "cuda_capability": "9.0"}
    ],
    "driver_version": "535.129.03",
    "cuda_version": "12.2"
  }
}
```

If `nvidia-smi` returns nothing, omit the entire `gpu` key.

### 2.3 `local_tools`

```json
{
  "local_tools": {
    "boltzgen": {
      "detected": true,
      "path": "/data/proteus/proteus-design",
      "conda_env": "bg",
      "version": "1.2.0",
      "weights_present": true,
      "smoke_test_passed": true
    },
    "protenix": {
      "detected": true,
      "path": "/data/proteus/Protenix",
      "conda_env": "protenix",
      "version": "1.0.0",
      "model": "protenix_base_20250630_v1.0.0",
      "weights_present": true,
      "smoke_test_passed": true
    },
    "pxdesign": {
      "detected": false,
      "path": null,
      "conda_env": "pxdesign",
      "version": null,
      "weights_present": false,
      "smoke_test_passed": false,
      "error": "conda env 'pxdesign' does not exist"
    }
  }
}
```

For each tool block:

| Field | Type | Notes |
|-------|------|-------|
| `detected` | boolean | Path exists and conda env is present |
| `path` | string \| null | Install path |
| `conda_env` | string | Expected conda env name |
| `version` | string \| null | From `--version` if available |
| `weights_present` | boolean | Expected weights directory exists |
| `smoke_test_passed` | boolean | `<tool> --help` returned 0 |
| `error` | string | Present only if `detected: false` |

### 2.4 `providers_detected`

```json
{
  "providers_detected": {
    "local":    {"available": true,  "reason": "GPU + 2/3 tools detected"},
    "hpc":      {"available": false, "reason": "RUNPOD_API_KEY not set"},
    "tamarind": {"available": false, "reason": "TAMARIND_API_KEY not set"}
  }
}
```

Each provider has `available: boolean` + `reason: string`. The status display
reads this to render the "Compute:" line.

### Staleness rule

If `now - last_scanned_at > 24h`, the session skill prints:

```text
⚠️  environment.json is 3 days stale. Run /by:setup to refresh.
```

But does NOT block the session.

---

## 3. Migration from pre-2026-05 Configs

Older configs may have:

- `compute.preferred_provider` instead of `compute.default_provider`
- `compute.preferred_provider == "tamarind"` (old default)
- No `providers_priority` key
- No `compute.hpc` block; instead `compute.ssh` was used

The validator emits these warnings:

| Old field | New field | Auto-fix? |
|---|---|---|
| `compute.preferred_provider` | `compute.default_provider` | yes, rename in place |
| `compute.preferred_provider: "tamarind"` (no explicit choice) | `compute.default_provider: "local"` | yes IF the user explicitly opts in |
| Missing `providers_priority` | Add `["local", "hpc", "tamarind"]` | yes |
| `compute.ssh.host` set, no `compute.hpc` | Move to `compute.hpc` with `target: "local_hpc"` | yes, but warn user |

Run `init_questionnaire.py --defaults --keep-existing` to apply migrations
without nuking unrelated fields.

---

## 4. Quick Validation Checklist

When in doubt, check:

- [ ] `compute.default_provider` is one of `local`, `hpc`, `tamarind`, `auto`
- [ ] `compute.providers_priority` lists `local` first by default
- [ ] If `default_provider == "hpc"`, `hpc.target` and `hpc.api_key_env` are set
- [ ] `model_profile` is one of `quality`, `balanced`, `budget`
- [ ] `workflow.default_campaign_tier` is one of `preview`, `standard`, `production`
- [ ] `safety.require_plan_approval` is `true` (warn if `false`)
- [ ] `safety.require_lab_approval` is `true` (warn if `false`)
- [ ] `.by/environment.json` `last_scanned_at` is within 24h (else suggest `/by:setup`)
