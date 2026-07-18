# The6Pillars

A multi-agent CLI that reviews your AWS Terraform plan against the 6 pillars of the
[AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/) —
Security, Reliability, Performance Efficiency, Cost Optimization, Operational Excellence, and
Sustainability.

Six specialist agents (one per pillar) independently review your `terraform plan`, a reconciler
agent surfaces the cases where two pillars' recommendations conflict (e.g. Security wants
Multi-AZ, Cost flags the doubled spend), and the CLI prints a triaged report — what's blocking,
what's a genuine tradeoff for you to decide, and what passed clean.

```
$ pillars review ./infra

Synthesizing... (terraform plan)  ✓ 14 resources

Pillar review
  ⚠ Security                 2 findings (1 blocking)
  ⚠ Reliability               1 finding
  ✓ Cost Optimization
  ✓ Performance Efficiency
  ✓ Operational Excellence
  ✓ Sustainability

BLOCKING (1)
  • aws_s3_bucket.data — public access not blocked
      → add an aws_s3_bucket_public_access_block resource

YOUR CALL (1)
  • aws_db_instance.main — single-AZ, no automated failover
      → accept the risk, or set multi_az = true (+~$15/mo)

PASSED — Cost Optimization, Performance Efficiency, Sustainability, Operational Excellence clean
```

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Set your Anthropic API key (get one at [console.anthropic.com](https://console.anthropic.com)):

```sh
cp .env.example .env
# edit .env and add ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

Review a Terraform directory directly (requires `terraform` and AWS credentials configured):

```sh
pillars review ./path/to/your/terraform
```

Or review a pre-generated plan without needing Terraform/AWS credentials at all — handy for
trying it out:

```sh
pillars review ./examples/demo-infra --plan-json ./examples/demo-infra/plan.json
```

The bundled `examples/demo-infra` is a deliberately flawed sample (public S3 bucket, hardcoded
DB password, single-AZ database with no backups) so you can see the tool actually catch things.

## How it works

1. `terraform plan` + `terraform show -json` produces the plan, trimmed down to just the changed
   resources ([terraform.py](src/pillars/terraform.py)).
2. Six pillar agents review the same resource list in parallel, each scoped to its own rubric
   ([agents/rubrics/](src/pillars/agents/rubrics/)), and return structured findings.
3. A reconciler agent looks across all six findings sets for the same resource and flags genuine
   cross-pillar conflicts, resolving the clear-cut ones and leaving true tradeoffs as "your call."
4. The CLI renders a triaged terminal report ([render.py](src/pillars/render.py)).

Built on the [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) using
`claude-sonnet-5` with native structured outputs — no framework, just parallel API calls plus a
reconciliation pass.

## Status

v1 — reviews a single Terraform plan end-to-end. Not yet built: CDK support, resource-type
routing (to skip irrelevant pillars on small diffs), a `.pillars.yml` priority config, and
interactive follow-up (`pillars chat`).

## Testing

```sh
pytest
```
