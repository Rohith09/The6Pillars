# Implementation Plan: Terraform Redaction Before LLM Payloads

## 1. Executive summary

PR 1 should be a narrow upstream contribution that prevents sensitive Terraform plan values from entering normalized Terraform resources and LLM prompt payloads.

The current Terraform path copies `resource_changes[].change.after` into `ResourceChange.after`, and the agent runner serializes `ResourceChange` objects into LLM messages. PR 1 should add a sanitizer at the Terraform normalization seam, using Terraform `after_sensitive` metadata plus conservative key-name heuristics.

PR 1 must not change CLI behavior, model types, report rendering, CloudFormation normalization, dependencies, commits, or provider architecture.

## 2. Current repository architecture

Confirmed repository facts:

- CLI entry point: `pyproject.toml` exposes `pillars = "pillars.cli:app"`.
- CLI command: `src/pillars/cli.py` defines `review()`.
- Terraform plan flow: `src/pillars/terraform.py` runs or loads Terraform plan JSON, extracts references, and normalizes resources.
- Shared resource model: `src/pillars/models.py` defines `ResourceChange.after` as `dict | None`.
- Agent payload flow: `src/pillars/agents/runner.py` serializes normalized `ResourceChange` objects with `_resources_payload()`.
- CloudFormation flow: `src/pillars/cloudformation.py` normalizes template resources separately and is out of scope for PR 1.
- Reports: `src/pillars/render.py` and `src/pillars/render_html.py` render LLM-generated findings, not raw normalized resource values.
- Existing tests cover Terraform normalization, CloudFormation normalization, context loading, diagrams, live display phrases, terminal rendering, and HTML rendering.
- No CI workflow files are present in this working tree.

## 3. Current Terraform-to-LLM data flow

1. `pillars review --plan-json` loads JSON and calls `terraform.normalize(plan)`.
2. `pillars review <directory>` calls `terraform.run_plan(path)` and then `terraform.normalize(plan)`.
3. `terraform.normalize()` skips ignored actions, derives provider shorthand, attaches references, and creates `ResourceChange`.
4. `ResourceChange.after` currently receives raw `change.after`.
5. `review_with_animation()` passes normalized resources to each pillar agent.
6. `run_pillar_agent()` calls `_resources_payload(resources)`.
7. `_resources_payload()` serializes `ResourceChange` objects into JSON for the LLM prompt.
8. LLM-generated findings are grouped into a report and rendered to HTML/terminal output.

Security risk:

- A sensitive value copied into `ResourceChange.after` can be sent to the configured LLM.
- If the LLM echoes the value, it can appear in generated reports or terminal output.

## 4. Identified security risks

Confirmed risks:

- `src/pillars/terraform.py` does not inspect Terraform `after_sensitive` metadata.
- `examples/demo-infra/plan.json` contains a synthetic database password in `change.after.password` with no `after_sensitive` field.
- `_resources_payload()` currently serializes normalized resources exactly as provided.

Explicit PR 1 non-goals:

- CloudFormation template values are not sanitized in PR 1.
- `.pillars/context.md` user context is not sanitized in PR 1.
- Report renderers are not changed in PR 1 because the safety seam is before LLM prompt construction.

## 5. Recommended sanitization architecture

Add `src/pillars/sanitize.py` as a small, deep module with these public names:

```python
REDACTED_VALUE = "[REDACTED]"

def is_sensitive_key(key: str) -> bool: ...
def sanitize_value(value: Any, sensitivity: Any = None) -> Any: ...
def sanitize_after(after: dict | None, after_sensitive: Any = None) -> dict | None: ...
```

Integrate it only in `terraform.normalize()`:

- Read `change = rc.get("change", {})` once.
- Use `sanitize_after(change.get("after"), change.get("after_sensitive"))`.
- Pass the sanitized dict-or-None into `ResourceChange.after`.

This keeps `ResourceChange.after` as `dict | None` and prevents raw Terraform values from reaching the shared normalized resource list.

## 6. Sanitization behavior

Terraform sensitivity metadata:

- If sensitivity metadata is `True` and the corresponding value is a scalar, return `"[REDACTED]"`.
- If sensitivity metadata is `True` and the corresponding value is a dict, preserve the dict keys and recursively redact every contained value.
- If sensitivity metadata is `True` and the corresponding value is a list, preserve list length/order and recursively redact every contained value.
- If sensitivity metadata is a dict and the value is a dict, recurse by matching keys.
- If sensitivity metadata is a list and the value is a list, recurse by index.
- Missing, incomplete, malformed, or shape-mismatched metadata must not raise.

Sensitive key-name fallback:

- Apply fallback during traversal even when sensitivity metadata is missing or malformed.
- Key matching must support snake_case, kebab-case, camelCase, PascalCase, and compact names.
- Sensitive examples that must match: `api_key`, `api-key`, `apiKey`, `ApiKey`, `apikey`, `dbpassword`, `accesstoken`, `privatekey`, `password`, `passwd`, `token`, `clientSecret`, `connectionString`, `authorization`, `user_data`.
- Safe identifiers that must not be redacted: `public_key`, `key_name`, `secret_name`, `secret_id`, `secret_arn`, `secret_version`, including equivalent case/separator forms.

Copy behavior:

- Sanitization must return new dict/list containers.
- Source plan data must not be mutated.
- `sanitize_after()` must return only a dict or `None`.
- If top-level `after` is a dict and top-level sensitivity is `True`, preserve the top-level object shape and redact all contained values.

## 7. Exact PR 1 file scope

Allowed files:

- Add `src/pillars/sanitize.py`.
- Modify `src/pillars/terraform.py`.
- Add `tests/test_sanitize.py`.
- Modify `tests/test_terraform_normalize.py`.
- Add `tests/test_agents_runner.py`.
- Modify `README.md`.

Do not modify:

- `src/pillars/cli.py`.
- `src/pillars/models.py`.
- `src/pillars/cloudformation.py`.
- `tests/test_render.py`.
- `tests/test_render_html.py`.
- Dependency configuration.

## 8. Proposed APIs and integration details

`sanitize_value(value, sensitivity=None)`:

- General recursive sanitizer used by tests and by `sanitize_after()`.
- Handles scalar, dict, list, `None`, and malformed sensitivity metadata.
- Redacts by sensitivity metadata and by key-name fallback.

`sanitize_after(after, after_sensitive=None)`:

- Terraform-specific wrapper preserving `ResourceChange.after: dict | None`.
- Returns `None` when `after is None`.
- Returns a sanitized dict when `after` is a dict.
- Defensively returns `None` for unexpected non-dict top-level `after` values rather than widening the model type.

`terraform.normalize(plan_json)`:

- Use `change = rc.get("change", {})`.
- Keep existing action filtering.
- Keep existing provider shorthand logic.
- Keep existing reference extraction.
- Set `after=sanitize_after(change.get("after"), change.get("after_sensitive"))`.

## 9. Test matrix

### `tests/test_sanitize.py`

Cover:

- Sensitive scalar becomes `"[REDACTED]"`.
- `True` sensitivity on dict/list preserves structure and redacts contained scalar leaves.
- Nested dicts and nested lists.
- Partially sensitive objects preserve safe fields.
- `None`, empty dict, and empty list.
- Missing, malformed, incomplete, and shape-mismatched sensitivity metadata.
- Sensitive key fallback when metadata is absent.
- Case and separator variants: snake_case, kebab-case, camelCase, PascalCase.
- Compact sensitive names: `apikey`, `dbpassword`, `accesstoken`, `privatekey`.
- Safe identifiers remain unchanged: `public_key`, `key_name`, `secret_name`, `secret_id`, `secret_arn`, `secret_version`.
- Source input is not mutated.

### `tests/test_terraform_normalize.py`

Cover:

- `after_sensitive` redacts recursively while keeping `ResourceChange.after` as a dict.
- Missing `after_sensitive` still uses key fallback.
- Raw synthetic values do not appear in normalized model dumps.
- Safe Terraform values remain unchanged.
- References remain preserved.
- Ignored Terraform actions remain ignored.
- Input plan is not mutated.

### `tests/test_agents_runner.py`

Cover:

- Normalize a synthetic Terraform plan containing raw secrets.
- Pass normalized resources to `_resources_payload()`.
- Assert the payload contains `"[REDACTED]"`.
- Assert raw synthetic values such as `super-secret-test-password`, `test-api-token-value`, and `fake-private-key-material` are absent.
- Assert safe values and references remain present.

## 10. Backwards compatibility

Unchanged:

- CLI options and behavior.
- `ResourceChange.after` type.
- Report rendering.
- CloudFormation normalization.
- Terraform ignored-action filtering.
- Reference extraction.
- Dependencies and packaging.

Intentional change:

- Sensitive Terraform values are replaced before normalized Terraform resources are sent to agents.
- Security agents still see the sensitive attribute names and redaction markers, preserving the signal that a secret-like value exists without exposing the value.

## 11. CLI design decision

PR 1 uses always-on Terraform sanitization with no CLI flag and no unsafe override.

Rejected for PR 1:

- `--redact-sensitive`.
- `--no-redact-sensitive`.
- Runtime warning/disclosure from `src/pillars/cli.py`.

Reason:

- The smallest safe upstream scope is an internal redaction guarantee plus documentation.

## 12. Error handling

- Sanitizer functions should not raise for malformed sensitivity metadata.
- Do not log raw values.
- Treat `True` sensitivity as authoritative.
- Treat missing, `False`, `None`, malformed, or mismatched metadata as non-sensitive metadata while still applying key fallback.
- Preserve normalized top-level `after` as a dict or `None`.

## 13. README documentation

README must explicitly state:

- Terraform values are sanitized before LLM review.
- Sanitization uses Terraform sensitivity metadata and key-name heuristics.
- Non-sensitive Terraform resource data is still sent to the configured LLM provider.
- CloudFormation input and `.pillars/context.md` are not covered by this first Terraform redaction change.

Recommended location:

- Near Terraform usage or the "How it works" section, where the README explains normalized resource data and LLM review.

## 14. First upstream PR scope

Suggested title:

`feat: redact sensitive Terraform plan values before LLM review`

Include:

- Terraform sanitizer module.
- Terraform normalization integration.
- Unit tests for sanitizer behavior.
- Terraform normalization regression tests.
- LLM payload regression test.
- README security note.

Exclude:

- CloudFormation sanitization.
- Context sanitization.
- CLI flags or CLI output changes.
- Model type changes.
- Renderer test changes.
- Provider abstraction.
- JSON/SARIF output.
- Suppressions, baselines, GitHub integration, or deterministic rule engine.

## 15. Definition of Done

PR 1 is complete when:

- Terraform `change.after` values are sanitized before constructing `ResourceChange`.
- Terraform `after_sensitive` is handled recursively.
- `True` sensitivity preserves dict/list structure while redacting contained leaves.
- Key-name fallback supports separator, case, and compact variants.
- Safe identifiers are not over-redacted.
- Raw synthetic secrets do not appear in normalized resources or LLM payload tests.
- Existing Terraform references and ignored-action behavior are preserved.
- Inputs are not mutated.
- README documents coverage and non-coverage.
- Full pytest suite passes in the project virtual environment.
- `git diff --check` passes.

## 16. Future roadmap

After PR 1:

- Add JSON output and stable finding IDs.
- Add configurable CI failure threshold.
- Add accepted-risk suppressions with expiry.
- Add baseline support.
- Add GitHub Actions and SARIF.
- Consider CloudFormation and context sanitization as separate security PRs.
- For the EUHub fork, evaluate provider abstraction, deterministic rules, and optional runtime AWS context integrations.

## 17. Implementation order

1. Create or activate `.venv`.
2. Run `pip install -e ".[dev]"`.
3. Run current `pytest` and record the baseline.
4. Add failing `tests/test_sanitize.py`.
5. Add failing `tests/test_terraform_normalize.py` cases.
6. Add failing `tests/test_agents_runner.py`.
7. Implement `src/pillars/sanitize.py`.
8. Integrate sanitizer in `src/pillars/terraform.py`.
9. Update README.
10. Run targeted tests.
11. Run full `pytest`.
12. Run `git diff --check`.
13. Summarize changed files, tests, and remaining risks.

## 18. Risks and unresolved questions

Risks:

- Key-name heuristics can still miss provider-specific secret names.
- Key-name heuristics can still redact useful non-secret operational context.
- CloudFormation and `.pillars/context.md` remain possible sensitive-data paths until future work.

Resolved for PR 1:

- No CLI flags.
- No model type changes.
- No renderer changes.
- No CloudFormation sanitization.
- No new dependencies.

## 19. Branch and commit strategy

Current branch:

- `agent/redact-sensitive-terraform-values`

Suggested commit title if the user later asks to commit:

- `feat: redact sensitive Terraform plan values before LLM review`

Do not commit or push as part of PR 1 implementation unless explicitly requested later.

## 20. Console summary

Files inspected while preparing this plan:

- `src/pillars/terraform.py`
- `src/pillars/models.py`
- `src/pillars/agents/runner.py`
- `src/pillars/cli.py`
- `src/pillars/cloudformation.py`
- `src/pillars/render.py`
- `src/pillars/render_html.py`
- `tests/test_terraform_normalize.py`
- `README.md`
- `pyproject.toml`

Expected PR 1 changed files:

- `docs/implementation-plan.md`
- `src/pillars/sanitize.py`
- `src/pillars/terraform.py`
- `tests/test_sanitize.py`
- `tests/test_terraform_normalize.py`
- `tests/test_agents_runner.py`
- `README.md`
