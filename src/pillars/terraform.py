import json
import re
import subprocess
import tempfile
from pathlib import Path

from pillars.models import ResourceChange
from pillars.sanitize import sanitize_after

# actions that represent "nothing meaningfully changing" and aren't worth
# spending pillar-agent tokens on
_IGNORED_ACTIONS = {("no-op",), ("read",)}

_RESOURCE_REF = re.compile(r"^([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_-]+)")
_DATA_REF = re.compile(r"^data\.([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_-]+)")
_NON_RESOURCE_PREFIXES = ("var.", "local.", "module.", "count.", "each.", "path.", "terraform.")


class TerraformError(RuntimeError):
    pass


def run_plan(directory: Path) -> dict:
    """Run `terraform plan` + `terraform show -json` in `directory` and return the parsed plan."""
    if not (directory / ".terraform").exists():
        _run(["terraform", "init", "-input=false"], directory)

    with tempfile.TemporaryDirectory() as tmp:
        plan_path = Path(tmp) / "tfplan.bin"
        _run(["terraform", "plan", "-input=false", f"-out={plan_path}"], directory)
        result = _run(["terraform", "show", "-json", str(plan_path)], directory)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise TerraformError(f"Could not parse `terraform show -json` output: {e}") from e


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=False
        )
    except FileNotFoundError as e:
        raise TerraformError(
            "`terraform` was not found on PATH. Install it, or pass --plan-json instead."
        ) from e

    if result.returncode != 0:
        raise TerraformError(f"`{' '.join(cmd)}` failed:\n{result.stderr.strip()}")
    return result


def _base_address(ref: str) -> str | None:
    """Reduce a Terraform reference string (e.g. `aws_s3_bucket.data.arn`) to its resource
    address (`aws_s3_bucket.data`), or None if it isn't a resource/data-source reference."""
    if ref.startswith(_NON_RESOURCE_PREFIXES):
        return None
    if ref.startswith("data."):
        m = _DATA_REF.match(ref)
        return f"data.{m.group(1)}.{m.group(2)}" if m else None
    m = _RESOURCE_REF.match(ref)
    return f"{m.group(1)}.{m.group(2)}" if m else None


def _collect_refs(node: object) -> set[str]:
    """Recursively walk a Terraform `expressions` block, collecting every string found in a
    `"references"` array."""
    refs: set[str] = set()
    if isinstance(node, dict):
        raw = node.get("references")
        if isinstance(raw, list):
            refs.update(r for r in raw if isinstance(r, str))
        for value in node.values():
            refs.update(_collect_refs(value))
    elif isinstance(node, list):
        for item in node:
            refs.update(_collect_refs(item))
    return refs


def extract_references(plan_json: dict) -> dict[str, list[str]]:
    """Map each resource address to the other resource addresses it references, derived from
    the plan's `configuration.root_module.resources[].expressions` blocks."""
    root = plan_json.get("configuration", {}).get("root_module", {})
    result: dict[str, list[str]] = {}
    for res in root.get("resources", []):
        address = res.get("address")
        if not address:
            continue
        raw_refs = _collect_refs(res.get("expressions", {}))
        bases = {_base_address(r) for r in raw_refs}
        bases.discard(None)
        bases.discard(address)
        result[address] = sorted(bases)
    return result


def normalize(plan_json: dict) -> list[ResourceChange]:
    """Trim a raw `terraform show -json` plan down to the fields pillar agents need."""
    references_map = extract_references(plan_json)
    resources: list[ResourceChange] = []
    for rc in plan_json.get("resource_changes", []):
        change = rc.get("change", {})
        actions = tuple(change.get("actions", []))
        if actions in _IGNORED_ACTIONS or not actions:
            continue

        provider_name = rc.get("provider_name", "")
        provider_short = provider_name.rsplit("/", 1)[-1] if provider_name else "unknown"

        resources.append(
            ResourceChange(
                address=rc["address"],
                type=rc["type"],
                name=rc["name"],
                provider=provider_short,
                actions=list(actions),
                after=sanitize_after(change.get("after"), change.get("after_sensitive")),
                references=references_map.get(rc["address"], []),
            )
        )
    return resources
