from pathlib import Path

from cfn_tools import load_json, load_yaml

from pillars.models import ResourceChange


def parse_template(path: Path) -> dict:
    text = path.read_text()
    if path.suffix.lower() in (".yaml", ".yml"):
        return load_yaml(text)
    return load_json(text)


def normalize(template: dict) -> list[ResourceChange]:
    resources: list[ResourceChange] = []
    for logical_id, resource in template.get("Resources", {}).items():
        resources.append(
            ResourceChange(
                address=logical_id,
                type=resource.get("Type", "Unknown"),
                name=logical_id,
                provider="aws",
                actions=["template"],
                after=resource.get("Properties", {}),
            )
        )
    return resources
