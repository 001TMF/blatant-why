# Security Audit Report — BY (Blatant-Why)

**Date:** 2026-03-25
**Scope:** Full codebase security analysis
**Method:** 6-agent parallel sweep (secrets, injection, MCP servers, supply chain, safety gates, data validation)

---

## Executive Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 8 |
| HIGH | 9 |
| MEDIUM | 12 |
| LOW | 8 |

The codebase has **no hardcoded secrets** and the **triple-layer lab safety gate is intact** (no bypass found). However, there are significant risks in command injection via SSH, path traversal in campaign/export code, unsafe NumPy pickle deserialization, and unpinned Python dependencies.

---

## CRITICAL Findings

### C1. Command Injection via SSH Paths
- **File:** `src/proteus_cli/ssh_runner.py:81,114,164`
- **Issue:** User-controlled paths interpolated into SSH commands via f-strings without escaping. `subprocess.run()` uses list args (good), but the remote command is a single unescaped string interpreted by the remote shell.
- **Attack:** `remote_workspace = "/tmp/job; rm -rf /"` → executed on remote host.
- **Fix:** Use `shlex.quote()` for all path variables in SSH command strings.

### C2. Path Traversal in Campaign Export
- **File:** `src/proteus_cli/campaign/export.py:92-369`
- **Issue:** `output_path` parameter in `export_fasta()`, `export_csv()`, `export_campaign_summary()` written without validating it's within the campaign directory.
- **Attack:** `output_path = "../../../../etc/cron.d/backdoor"` → arbitrary file write.
- **Fix:** Resolve path and validate it starts with the campaign base directory.

### C3. NumPy Pickle Deserialization (RCE)
- **File:** `src/proteus_cli/scoring/ipsae.py:162`
- **Issue:** `np.load(npz_path, allow_pickle=True)` on untrusted NPZ files enables arbitrary code execution via crafted pickle payloads.
- **Fix:** Use `allow_pickle=False`. If pickle is required, implement a restricted unpickler.

### C4. Path Traversal in Campaign Server
- **File:** `mcp_servers/campaign/server.py:374-376,653-672`
- **Issue:** `campaign_dir` parameter passed to file operations without validating it's within an authorized base directory.
- **Fix:** Validate `Path(campaign_dir).resolve()` is under the campaigns root.

### C5. Approval File TTL Bypass (Safety Gate Weakness)
- **File:** `mcp_servers/adaptyv/server.py:160-217`
- **Issue:** Approval file not consumed after use (no atomic check-and-consume). Can be reused within the 1-hour TTL window for multiple submissions.
- **Fix:** Rename approval file to `.consumed` after first use; implement per-submission nonces.

### C6. SSH Password Storage in Plaintext
- **File:** `mcp_servers/cloud/server.py:162-187`
- **Issue:** SSH passwords accepted from `~/.by/config.json` in plaintext, used directly for authentication.
- **Fix:** Remove password auth support; enforce SSH key-based auth only.

### C7. Subprocess Injection via `extra_args`
- **File:** `mcp_servers/local_compute/server.py:406-425,480-489,553-562`
- **Issue:** `extra_args.split()` passes user-controlled arguments to subprocess without validation or proper shell-aware parsing.
- **Fix:** Use `shlex.split()` or whitelist allowed flags.

### C8. Unpinned Python Dependencies (No Lock File)
- **File:** `pyproject.toml:6-16`
- **Issue:** All Python deps use `>=` constraints with no lock file committed. Supply chain attack via compromised upstream package.
- **Fix:** Generate and commit `uv.lock` or `poetry.lock`.

---

## HIGH Findings

### H1. Disabled SSH Host Key Verification (MITM)
- **Files:** `mcp_servers/local_compute/server.py:117-119`, `mcp_servers/cloud/server.py:169`
- **Issue:** `StrictHostKeyChecking=no` and `AutoAddPolicy()` disable MITM protection.
- **Fix:** Use `StrictHostKeyChecking=accept-new` or maintain known_hosts.

### H2. SSRF via External API Calls
- **Files:** `mcp_servers/pdb/server.py`, `tamarind/server.py`, `sabdab/server.py`, `research/server.py`, `uniprot/server.py`
- **Issue:** HTTP requests to external APIs without URL validation or internal IP blocklisting.
- **Fix:** Blocklist internal IPs (127.0.0.1, 169.254.x.x, 10.0.0.0/8); enforce HTTPS-only.

### H3. No Authentication on MCP Servers
- **Files:** All MCP servers
- **Issue:** No caller identity or authorization checks. Any process can invoke any tool.
- **Fix:** Add API key validation or caller identity verification.

### H4. Quote Injection in TypeScript execSync
- **File:** `src/init-cli/verify.ts:20`
- **Issue:** File path interpolated into shell command string with double quotes. Path containing `"` breaks out of quoted context.
- **Fix:** Use `spawnSync()` with array args instead of `execSync()` with string interpolation.

### H5. Unescaped SCP Paths
- **File:** `src/proteus_cli/ssh_runner.py:59-63`
- **Issue:** Local and remote paths passed to SCP without escaping spaces or special characters.
- **Fix:** Use `shlex.quote()` for path arguments.

### H6. Unsafe `cmd.split()` for Subprocess
- **File:** `src/proteus_cli/campaign/state.py:85-92`
- **Issue:** `_get_cmd_output()` uses `cmd.split()` which breaks on paths with spaces.
- **Fix:** Use `shlex.split()` or pass command as a list.

### H7. Unverified GitHub URLs for External Tools
- **File:** `plugin-manifest.json:7-24`
- **Issue:** Protenix, PXDesign, BoltzGen referenced without commit SHA, version tag, or integrity hash.
- **Fix:** Pin to specific tags/SHAs; add integrity hashes.

### H8. Pip Install Without Hash Verification
- **File:** `setup.sh:29`
- **Issue:** `pip install` without `--require-hashes` or version pinning. Errors suppressed with `2>/dev/null`.
- **Fix:** Use lock file with `--require-hashes`.

### H9. JSON Deserialization Without Schema Validation
- **Files:** `src/proteus_cli/campaign/state.py:161`, `export.py`, `decisions.py`
- **Issue:** JSON loaded and unpacked into dataclasses without field-level validation.
- **Fix:** Use Pydantic models for schema enforcement (already a dependency).

---

## MEDIUM Findings

| ID | File | Issue |
|----|------|-------|
| M1 | `adaptyv/server.py:172` | Path not normalized — campaign_dir accepted without bounds validation |
| M2 | `adaptyv/server.py:44-45` | Asymmetric TTLs (1h approval vs 5m confirmation) allows stale approvals |
| M3 | `adaptyv/server.py:196-206` | No clock skew protection on approval timestamps |
| M4 | `adaptyv/server.py:76-78` | Weak confirmation code entropy (24 bits / 16M codes — brute-forceable) |
| M5 | `tamarind/server.py:221-232` | File upload extension whitelist without content/magic-byte validation |
| M6 | `campaign/server.py:815-817` | JSON input parsed without size limits (DoS vector) |
| M7 | `config.py:201-206` | YAML config paths (ssh_key_path) not validated for traversal |
| M8 | `export.py:26`, `active_learning.py:62` | `glob()`/`rglob()` follows symlinks — can exfiltrate data |
| M9 | Multiple servers | API error responses leak internal details (paths, tokens) |
| M10 | `active_learning.py:68-69` | Generic exception handling masks permission errors |
| M11 | Multiple servers | No rate limiting on API calls or confirmation attempts |
| M12 | `adaptyv/server.py:98-100` | Audit logs only to stderr (transient, lost on restart) |

---

## LOW Findings

| ID | File | Issue |
|----|------|-------|
| L1 | `ssh_runner.py:158` | Truncated UUID (`uuid4()[:8]`) reduces job ID entropy |
| L2 | `config.py:213` | Missing explicit `Dumper=yaml.SafeDumper` on YAML dump |
| L3 | `main.py:15,28,41` | No file size or extension checks on CLI path args |
| L4 | `export.py:211` | CSV formula injection — design names not escaped for `=+@` |
| L5 | All external API servers | Hardcoded API URLs not configurable via env |
| L6 | PDB, UniProt, SAbDab | Missing User-Agent header on HTTP requests |
| L7 | `.planning/screening_gates.md` | Screening gate spec not implemented in code |
| L8 | `adaptyv/server.py:400-404` | Minor race condition in expired entry cleanup |

---

## Code Defect (Non-Security)

### `state.py:111-112` — Indentation Bug
- **Issue:** Line 112 references undefined variable `key` due to incorrect indentation inside a for loop.
- **Impact:** `NameError` on campaign initialization. Not a security issue but blocks functionality.

---

## Positive Findings

- **No hardcoded secrets** found in any file
- **YAML loading** correctly uses `yaml.safe_load()` everywhere
- **No `pickle.load()`** in production code (only numpy's allow_pickle, flagged above)
- **`subprocess.run()`** consistently uses list args, never `shell=True`
- **`.gitignore`** properly excludes `.env`, `.env.local`, settings files, campaign data
- **Triple-layer lab safety gate** has no complete bypass — all three layers enforced
- **Confirmation codes** use `secrets.token_hex()` (cryptographic randomness)
- **Two-step submission** (prepare → confirm) prevents accidental lab submissions

---

## Remediation Priority

### Immediate (Before Next Deploy)
1. Fix `np.load(allow_pickle=True)` → `allow_pickle=False` (C3)
2. Add `shlex.quote()` to SSH command construction (C1, H5)
3. Add path traversal validation to export functions (C2)
4. Add path validation to campaign server `campaign_dir` (C4)

### Urgent (Next Sprint)
5. Consume approval file after use (C5)
6. Remove SSH password auth (C6)
7. Use `shlex.split()` for `extra_args` (C7)
8. Generate and commit Python lock file (C8)
9. Pin external tool versions in plugin-manifest.json (H7)
10. Enable SSH host key checking (H1)

### Standard (Regular Cycle)
11. Add schema validation for JSON deserialization (H9)
12. Implement rate limiting on MCP servers (M11)
13. Add persistent audit logging (M12)
14. Block SSRF to internal IPs (H2)
15. Switch `execSync` to `spawnSync` in verify.ts (H4)

---

*Generated by 6-agent security analysis swarm on 2026-03-25*
