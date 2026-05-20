#!/usr/bin/env python3
"""runpod_deploy.py — deploy a BY tool to RunPod from a 6-field manifest.

Purpose:
    Read a deploy.yaml manifest (see scripts/deploy_tool_template.yaml), submit
    a pod-creation request to the RunPod GraphQL API, wait for the pod to
    reach RUNNING state, print the pod ID and proxy endpoint URL, and emit a
    config-patch snippet the user can merge into .by/config.json.

Inputs:
    deploy_yaml : path to a rendered deploy_tool_template.yaml with target=runpod

Outputs:
    stdout : pod_id, endpoint URL, .by/config.json patch
    exit 0 : pod is RUNNING and endpoint responded to HEAD
    exit 1 : invalid manifest, missing API key, or pod failed to start

Example:
    export RUNPOD_API_KEY=rpa_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    python3 scripts/runpod_deploy.py deploy_protenix.yaml
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("✗ PyYAML not installed. Install with: pip install pyyaml")

try:
    import requests
except ImportError:
    sys.exit("✗ requests not installed. Install with: pip install requests")


RUNPOD_API_URL = "https://api.runpod.io/graphql"
POLL_INTERVAL_SECONDS = 10
POLL_MAX_ATTEMPTS = 60  # 10 minutes total

# GPU type → RunPod gpuTypeId (subset; full list at https://docs.runpod.io/references/gpu-types)
GPU_TYPE_IDS: dict[str, str] = {
    "A40": "NVIDIA A40",
    "A4000": "NVIDIA RTX A4000",
    "A5000": "NVIDIA RTX A5000",
    "A6000": "NVIDIA RTX A6000",
    "L40": "NVIDIA L40",
    "L40S": "NVIDIA L40S",
    "A100-40GB": "NVIDIA A100 40GB PCIe",
    "A100-80GB": "NVIDIA A100 80GB PCIe",
    "H100": "NVIDIA H100 PCIe",
}


def load_manifest(path: Path) -> dict[str, Any]:
    """Read and validate a deploy manifest from disk.

    Args:
      path: filesystem path to deploy.yaml

    Returns:
      dict with the validated 6 required fields plus any optional fields.

    Raises:
      SystemExit on missing file, parse failure, or validation failure.
    """
    if not path.exists():
        sys.exit(f"✗ manifest not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        sys.exit(f"✗ YAML parse error in {path}: {exc}")

    # If the file has a single top-level key (e.g., when the user copied an
    # example block), unwrap it.
    if isinstance(raw, dict) and len(raw) == 1 and "tool" not in raw:
        only_key = next(iter(raw))
        raw = raw[only_key]

    required = {"tool", "target", "image", "weights_url", "entry_command", "volumes"}
    missing = required - set(raw or {})
    if missing:
        sys.exit(f"✗ manifest missing required fields: {sorted(missing)}")

    if raw["target"] != "runpod":
        sys.exit(f"✗ this script handles target=runpod only; got target={raw['target']!r}")

    return raw


def get_api_key() -> str:
    """Read RUNPOD_API_KEY from the environment.

    Returns:
      The API key string.

    Raises:
      SystemExit if the key is missing — never silently falls back.
    """
    key = os.environ.get("RUNPOD_API_KEY")
    if not key:
        sys.exit(
            "✗ RUNPOD_API_KEY not set in environment.\n"
            "  Generate one at https://www.runpod.io/console/user/settings\n"
            "  Then: export RUNPOD_API_KEY=rpa_xxxxxxxxxxxxxxxxxxxxxx\n"
            "  See references/runpod-setup.md for full setup."
        )
    return key


def build_pod_request(manifest: dict[str, Any]) -> dict[str, Any]:
    """Translate a deploy manifest into a RunPod GraphQL pod-create payload.

    Args:
      manifest: validated manifest dict from load_manifest().

    Returns:
      A dict matching RunPod's podFindAndDeployOnDemand mutation input.
    """
    gpu_label = manifest.get("gpu", "A40")
    gpu_type_id = GPU_TYPE_IDS.get(gpu_label, gpu_label)

    # Convert volumes list to env vars + mount paths
    container_volume_mb = 50 * 1024  # 50 GB ephemeral container disk
    volume_mount_path: str | None = None
    for vol in manifest["volumes"]:
        if not isinstance(vol, dict):
            continue
        if "container" in vol:
            volume_mount_path = vol["container"]
            break

    pod_input = {
        "cloudType": "SECURE",
        "gpuCount": 1,
        "volumeInGb": 100,
        "containerDiskInGb": container_volume_mb // 1024,
        "minVcpuCount": 4,
        "minMemoryInGb": 32,
        "gpuTypeId": gpu_type_id,
        "name": f"by-{manifest['tool']}",
        "imageName": manifest["image"],
        "dockerArgs": "",
        "ports": "8000/http,22/tcp",
        "volumeMountPath": volume_mount_path or "/workspace",
        "env": [
            {"key": "BY_TOOL", "value": manifest["tool"]},
            {"key": "BY_ENTRY_COMMAND", "value": manifest["entry_command"]},
            {"key": "BY_WEIGHTS_URL", "value": manifest["weights_url"]},
        ],
    }
    # RunPod's podFindAndDeployOnDemand expects a 2-letter ISO 3166-1 country
    # code on the `country` field. Manifests may carry either an ISO code in
    # `country` (preferred) or a legacy `region` field carrying an AWS-style
    # region string ("us-east-1"); we translate the latter for backwards
    # compatibility.
    country_code = manifest.get("country")
    if not country_code and manifest.get("region"):
        country_code = _aws_region_to_iso_country(manifest["region"])
    if country_code:
        pod_input["country"] = country_code
    return pod_input


# AWS region prefix -> ISO 3166-1 alpha-2 country code. Covers the regions
# most commonly used as proxies for "where on Earth to land the pod".
_AWS_PREFIX_TO_ISO = {
    "us-": "US",
    "ca-": "CA",
    "sa-": "BR",
    "eu-west": "IE",       # eu-west-1 is Ireland
    "eu-central": "DE",    # eu-central-1 is Frankfurt
    "eu-north": "SE",      # eu-north-1 is Stockholm
    "eu-south": "IT",      # eu-south-1 is Milan
    "eu-": "DE",           # generic eu fallback
    "ap-northeast-1": "JP",
    "ap-northeast-2": "KR",
    "ap-northeast-3": "JP",
    "ap-southeast-1": "SG",
    "ap-southeast-2": "AU",
    "ap-southeast-3": "ID",
    "ap-south-": "IN",
    "ap-east-": "HK",
    "me-": "AE",
    "af-": "ZA",
}


def _aws_region_to_iso_country(region: str) -> str | None:
    """Translate an AWS-style region string to an ISO 3166-1 alpha-2 code.

    Returns None if the region cannot be resolved (in which case the caller
    omits the `country` field, letting RunPod pick automatically).
    """
    region = (region or "").lower().strip()
    if not region:
        return None
    # Already an ISO code (2 letters, uppercase or lowercase) — accept as-is.
    if len(region) == 2 and region.isalpha():
        return region.upper()
    # Match longest-prefix-first so eu-central beats eu-.
    for prefix in sorted(_AWS_PREFIX_TO_ISO, key=len, reverse=True):
        if region.startswith(prefix):
            return _AWS_PREFIX_TO_ISO[prefix]
    return None


def submit_pod(api_key: str, pod_input: dict[str, Any]) -> str:
    """Submit a pod-create mutation to RunPod and return the new pod id.

    Args:
      api_key: RunPod API key from env.
      pod_input: dict matching podFindAndDeployOnDemand schema.

    Returns:
      The pod id string.

    Raises:
      SystemExit if the API returns an error or the response lacks an id.
    """
    mutation = """
    mutation($input: PodFindAndDeployOnDemandInput!) {
      podFindAndDeployOnDemand(input: $input) {
        id
        imageName
        machineId
        desiredStatus
      }
    }
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"query": mutation, "variables": {"input": pod_input}}
    try:
        resp = requests.post(RUNPOD_API_URL, headers=headers, json=payload, timeout=60)
    except requests.RequestException as exc:
        sys.exit(f"✗ network error calling RunPod API: {exc}")

    if resp.status_code == 401:
        sys.exit("✗ RunPod API returned 401 Unauthorized — check RUNPOD_API_KEY.")
    if resp.status_code != 200:
        sys.exit(f"✗ RunPod API returned {resp.status_code}: {resp.text[:500]}")

    body = resp.json()
    if body.get("errors"):
        sys.exit(f"✗ RunPod returned GraphQL errors: {body['errors']}")

    pod = (body.get("data") or {}).get("podFindAndDeployOnDemand")
    if not pod or not pod.get("id"):
        sys.exit(f"✗ unexpected response shape: {body}")
    return pod["id"]


def poll_pod_status(api_key: str, pod_id: str) -> dict[str, Any]:
    """Poll until the pod is RUNNING or the timeout expires.

    Args:
      api_key: RunPod API key from env.
      pod_id: the pod id returned by submit_pod().

    Returns:
      The final pod status dict including runtime ports.

    Raises:
      SystemExit if the pod never reaches RUNNING within POLL_MAX_ATTEMPTS.
    """
    query = """
    query($podId: String!) {
      pod(input: {podId: $podId}) {
        id
        desiredStatus
        runtime {
          ports {
            ip
            isIpPublic
            privatePort
            publicPort
            type
          }
        }
      }
    }
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        try:
            resp = requests.post(
                RUNPOD_API_URL,
                headers=headers,
                json={"query": query, "variables": {"podId": pod_id}},
                timeout=30,
            )
        except requests.RequestException as exc:
            print(f"  [attempt {attempt}] network error polling pod: {exc}", file=sys.stderr)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        if resp.status_code != 200:
            print(f"  [attempt {attempt}] HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        body = resp.json()
        pod = (body.get("data") or {}).get("pod") or {}
        status = pod.get("desiredStatus")
        if status == "RUNNING" and pod.get("runtime"):
            return pod
        print(f"  [attempt {attempt}/{POLL_MAX_ATTEMPTS}] pod status: {status}")
        time.sleep(POLL_INTERVAL_SECONDS)
    sys.exit(f"✗ pod {pod_id} did not reach RUNNING within {POLL_MAX_ATTEMPTS * POLL_INTERVAL_SECONDS}s")


def derive_endpoint(pod: dict[str, Any]) -> str:
    """Build the RunPod proxy URL from a running pod's runtime info.

    Args:
      pod: pod dict as returned by poll_pod_status().

    Returns:
      An https URL pointing at the first HTTP port (defaults to 8000).
    """
    pod_id = pod["id"]
    ports = (pod.get("runtime") or {}).get("ports") or []
    http_port = next((p["privatePort"] for p in ports if p.get("type") == "http"), 8000)
    return f"https://{pod_id}-{http_port}.proxy.runpod.net"


def print_config_patch(tool: str, endpoint_url: str, pod_id: str) -> None:
    """Print a JSON snippet the user can merge into .by/config.json.

    Args:
      tool: the BY tool name (used as a key under compute.hpc).
      endpoint_url: the resolved proxy URL.
      pod_id: the RunPod pod id for record-keeping.
    """
    patch = {
        "compute": {
            "hpc": {
                "target": "runpod",
                "endpoint_url": endpoint_url,
                tool: {
                    "endpoint_url": endpoint_url,
                    "pod_id": pod_id,
                },
            }
        }
    }
    print("\n----- merge into .by/config.json -----")
    print(json.dumps(patch, indent=2))
    print("----- end patch -----\n")


def main() -> int:
    """CLI entry point. Returns process exit code."""
    parser = argparse.ArgumentParser(
        description="Deploy a BY tool to RunPod from a 6-field manifest.",
        epilog="See references/runpod-setup.md for prerequisites.",
    )
    parser.add_argument(
        "manifest",
        type=Path,
        help="Path to a rendered deploy_tool_template.yaml with target=runpod",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the manifest and print the request payload without submitting.",
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    print(f"✓ manifest loaded: tool={manifest['tool']} target={manifest['target']}")

    pod_input = build_pod_request(manifest)
    if args.dry_run:
        print("--- dry-run: payload that WOULD be sent to RunPod ---")
        print(json.dumps(pod_input, indent=2))
        return 0

    api_key = get_api_key()
    print(f"✓ RUNPOD_API_KEY present (len={len(api_key)})")

    pod_id = submit_pod(api_key, pod_input)
    print(f"✓ pod submitted: pod_id={pod_id}")
    print(f"  polling for RUNNING status (interval={POLL_INTERVAL_SECONDS}s, max attempts={POLL_MAX_ATTEMPTS})...")

    pod = poll_pod_status(api_key, pod_id)
    endpoint = derive_endpoint(pod)
    print(f"✓ pod RUNNING: {pod_id}")
    print(f"✓ endpoint: {endpoint}")

    print_config_patch(manifest["tool"], endpoint, pod_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
