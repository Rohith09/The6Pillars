import re
from pathlib import Path

from cfn_tools import load_json, load_yaml

from pillars.models import ResourceChange

_SUB_TOKEN = re.compile(r"\$\{([^}]+)\}")


def parse_template(path: Path) -> dict:
    text = path.read_text()
    if path.suffix.lower() in (".yaml", ".yml"):
        return load_yaml(text)
    return load_json(text)


def _extract_refs(node: object) -> set[str]:
    """Recursively walk a resource's Properties, collecting logical IDs referenced via
    Ref / Fn::GetAtt / Fn::Sub (skipping AWS pseudo parameters like AWS::Region)."""
    refs: set[str] = set()
    if isinstance(node, dict):
        ref = node.get("Ref")
        if isinstance(ref, str) and "::" not in ref:
            refs.add(ref)

        get_att = node.get("Fn::GetAtt")
        if isinstance(get_att, list) and get_att and isinstance(get_att[0], str):
            refs.add(get_att[0])
        elif isinstance(get_att, str):
            refs.add(get_att.split(".")[0])

        sub = node.get("Fn::Sub")
        sub_text = sub[0] if isinstance(sub, list) and sub else sub
        if isinstance(sub_text, str):
            for token in _SUB_TOKEN.findall(sub_text):
                base = token.split(".")[0]
                if "::" not in base:
                    refs.add(base)

        for value in node.values():
            refs.update(_extract_refs(value))
    elif isinstance(node, list):
        for item in node:
            refs.update(_extract_refs(item))
    return refs


def normalize(template: dict) -> list[ResourceChange]:
    resources: list[ResourceChange] = []
    for logical_id, resource in template.get("Resources", {}).items():
        properties = resource.get("Properties", {})
        references = sorted(_extract_refs(properties) - {logical_id})
        resources.append(
            ResourceChange(
                address=logical_id,
                type=resource.get("Type", "Unknown"),
                name=logical_id,
                provider="aws",
                actions=["template"],
                after=properties,
                references=references,
            )
        )
    return resources
