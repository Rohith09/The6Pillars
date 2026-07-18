import json
import subprocess
import tempfile
from pathlib import Path

from pillars.models import ResourceChange

# actions that represent "nothing meaningfully changing" and aren't worth
# spending pillar-agent tokens on
_IGNORED_ACTIONS = {("no-op",), ("read",)}


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


def normalize(plan_json: dict) -> list[ResourceChange]:
    """Trim a raw `terraform show -json` plan down to the fields pillar agents need."""
    resources: list[ResourceChange] = []
    for rc in plan_json.get("resource_changes", []):
        actions = tuple(rc.get("change", {}).get("actions", []))
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
                after=rc.get("change", {}).get("after"),
            )
        )
    return resources
