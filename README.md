# Empório da Música — customer service agent

> Final README (T16). It reports real results from runs with the Groq API. Anything not yet validated with the real model is marked as pending; nothing pending is presented as passed.

## Overview

Python prototype of a text-based customer service agent for the fictional store Empório da Música (Artefact technical challenge). The assistant, named Mel, talks to the customer in Brazilian Portuguese and answers questions about:

- the product catalog (search, details, categories, promotional price, PIX price and installments);
- orders (lookup with identity verification);
- store policies (opening hours, payment, exchanges and returns, shipping, warranty, privacy);
- general store information and handoff to a human agent.

The agent uses **function calling (tool use)**: the model decides when to call deterministic tools that query the CSV files or the policy manual. Every numeric rule (prices, installments, shipping, opening hours) is computed in Python; the model only writes the reply. When the manual or the data are contradictory or silent, the agent reports a limitation instead of inventing a rule.

## Requirements

- Python 3.13 (`requires-python = ">=3.13"`).
- A Groq API key (`GROQ_API_KEY`) to talk to the default model. Alternatively, an Anthropic key (`ANTHROPIC_API_KEY`) with `LLM_PROVIDER=anthropic`. The automated tests need no key.

## Installation

```bash
python -m venv venv
# Linux/macOS/Git Bash:        source venv/bin/activate   (Git Bash on Windows: source venv/Scripts/activate)
# PowerShell:                  venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env           # PowerShell: Copy-Item .env.example .env
```

Edit `.env` and fill in `GROQ_API_KEY`. The `.env` file is not versioned. The remaining variables have sensible defaults (see [.env.example](.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `groq` | AI provider (`groq` or `anthropic`; switchable by configuration) |
| `LLM_MODEL` | `openai/gpt-oss-120b` | model |
| `LLM_MAX_TOKENS` | `4096` | response token limit |
| `LLM_EFFORT` | `low` | reasoning depth (`low`, `medium`, `high`, `xhigh`, `max`); on Groq it maps to `reasoning_effort` for `gpt-oss` models (`xhigh` and `max` become `high`) |
| `LLM_REFUSAL_FALLBACK` | `true` | server-side refusal fallback (Anthropic provider only) |
| `GROQ_API_KEY` | empty | Groq API key (default provider) |
| `ANTHROPIC_API_KEY` | empty | Anthropic API key (only with `LLM_PROVIDER=anthropic`) |
| `REFERENCE_DATE` | empty | controlled date/time (see below) |
| `MAX_TOOL_ITERATIONS` | `6` | tool loop iteration limit |
| `MAX_HISTORY_TURNS` | `50` | history window |

To use Anthropic instead, set `LLM_PROVIDER=anthropic`, `LLM_MODEL=claude-sonnet-5-5`, `LLM_MAX_TOKENS=16000` and `ANTHROPIC_API_KEY`.

## Running

```bash
python -m emporio_agent            # interactive conversation
python -m emporio_agent --debug    # shows the tools called in each reply
python -m emporio_agent --save     # saves the conversation on exit
python -m emporio_agent --version
```

Commands inside the conversation (in Portuguese, like the rest of the customer-facing interface):

| Command | Effect |
|---|---|
| `/salvar` | saves the conversation to `runtime/transcripts/conversa-<date>-<id>.md` |
| `/nova` | starts a new conversation |
| `/ajuda` | lists the commands |
| `/sair` | exits |

By default the agent uses the real system date and time (time zone `America/Campo_Grande`). To reproduce a situation with a fixed date (tests and examples), set `REFERENCE_DATE` in `.env` in ISO 8601, for example `2026-03-25` or `2026-03-25T10:30`. Orders in the dataset go up to 2026-03-22; with the real date, every order already looks old.

Without an API key for the selected provider, the CLI exits with a clear message in Portuguese and exit code 2.

## Tests

```bash
python -m pytest -q          # full suite, never calls the real model
python -m pytest -q -m llm   # smoke tests against the real provider (require GROQ_API_KEY / ANTHROPIC_API_KEY)
```

Unit and integration tests use a fake LLM (`FakeLLM`); tests marked `llm` are skipped by default (`addopts = "-m 'not llm'"`). Current state: 1016 passing; 2 real-provider smoke tests skipped by default (`-m llm`).

## Utilities

```bash
python scripts/build_policies.py          # regenerates knowledge/policies.md from the PDF
python scripts/build_policies.py --check  # checks that the versioned .md is up to date with the PDF
python scripts/run_scenarios.py           # end-to-end scenarios with the real model (T14)
python scripts/run_scenarios.py --pause 60 --report runtime/scenarios.md   # spaced out, with a Markdown report
python scripts/record_example.py --script PATH --out PATH   # records a real example conversation (T15)
```

`scripts/run_scenarios.py` was delivered by T14 (contract in [ARCHITECTURE.md](ARCHITECTURE.md), §5.9.1). It requires an API key (exit code 2 without one) and accepts `--only` (scenario ids, e.g. `5,9`), `--repeat` (default 2), `--reference-date` (default `2026-03-25T10:00`), `--pause SECONDS` (pause between scenarios and repetitions, default 60) and `--report` (writes a Markdown report to the given path). The pause exists because of the Groq per-minute rate limits (see decision D17 below).

## Architecture overview

```
Customer → CLI (cli.py) → Agent (tool-use loop + Session)
                            ├─ llm/     provider adapter (Groq by default, Anthropic as alternative)
                            └─ tools/   8 typed tools
                                 ├─ data/     CSVs loaded in memory (pandas), read-only
                                 ├─ domain/   pure rules: prices, PIX, installments, hours, shipping
                                 └─ policies/ sections of knowledge/policies.md (generated from the PDF)
```

Principles: the original `data/` is never modified; the LLM writes and Python computes; dependencies flow one way (`cli → agent → tools → data | domain | policies`); everything is testable without an LLM except the loop itself (tested with a fake LLM); no agent framework, database or vector store. Details, folder structure and contracts between modules: [ARCHITECTURE.md](ARCHITECTURE.md).

## Technical decisions

Full rationale in [TECHNICAL_DECISIONS.md](TECHNICAL_DECISIONS.md).

- **Agent approach (D1).** Function calling with a custom loop of about 100 lines and an iteration limit. Rejected: SQL agent (room for wrong queries and it exposes the customer table), pure RAG (price and stock need exactness and numeric filters) and LangChain/LangGraph/LlamaIndex (abstraction with no gain at this size). Every query decision is observable in the tool log (`--debug`).
- **Calculations in Python (D4).** Promotional price, PIX, installments, shipping and "open now?" come out of the tools ready to use, with `Decimal` and `ROUND_HALF_UP` rounding. The manual treats incorrect information as false advertising, and models make arithmetic and date mistakes.
- **Default provider: Groq (D5, D17).** The decision to use Groq came from the user. `LLM_PROVIDER=groq` selects the adapter in `llm/groq_client.py` (official `groq` SDK) behind a thin `LLMClient` interface; provider and model are switchable by configuration.
  - Model `openai/gpt-oss-120b`: a Groq production model (not preview) with tool use support and a `reasoning_effort` parameter (`low|medium|high`), mapped from `LLM_EFFORT`. A configurable alternative is `llama-3.3-70b-versatile` (production, parallel tool calls).
  - `LLM_MAX_TOKENS=4096`: Groq's per-minute throughput limit (Developer plan baseline: 8K tokens/min for `gpt-oss-120b`) makes reserving 16000 tokens unworkable.
  - Rate limits and resilience: HTTP 429 with `retry-after` is handled by the SDK (`max_retries=5`); a malformed tool call generated by the model (`tool_use_failed`) is retried once before becoming an error; `run_scenarios.py --pause` spaces out the scenarios.
  - The `gpt-oss` reasoning is neither returned nor resent (`include_reasoning=false`): Groq does not document resending it, so the history keeps only text and tool calls.
- **Anthropic as an alternative (D5, D16).** The Anthropic adapter remains (`LLM_PROVIDER=anthropic`, `claude-sonnet-5-5`). D16 applies only to it: no `temperature`/`top_p`/`top_k` and no forced `tool_choice` (the model rejects them), adaptive reasoning with `low` effort by default, `max_tokens` 16000, reasoning blocks resent unchanged in the history, prompt caching only on the stable system prefix. Since there is no `temperature`, the evaluation criteria check facts and tools called, not exact text.
- **Policy retrieval (D2).** The PDF is converted offline into `knowledge/policies.md` (reviewed and versioned) and split by section into fixed topics. The `consultar_politica(topico)` tool takes an `enum` of topics and returns the full text of the section. It is deterministic and auditable. Embeddings were rejected: with about 10 sections, a well-described enum retrieves better and with no risk of returning the wrong passage.
- **Prompt strategy (D10).** The system prompt defines the persona (Mel, no emojis), the scope (only the store's instruments), the grounding rule (price, stock and delivery time only via tools), polite refusal of unrelated topics, and the duty to pass on the limitations returned by the tools. The manual's conduct rules go in the prompt; policy content comes through a tool. There is no separate intent classifier. Prompt injection defense lives in the tool layer, not in the prompt.
- **Data handling (D3, D8).** pandas in memory, no database; corrections and normalizations only in memory. An order lookup requires the order number plus an email or phone that matches the customer of that order, and never returns contact details or the address. A customer is never identified by name or email alone (customers 11 and 43 share an email).
- **History (D7).** In-memory history per session (needed for follow-ups such as "and in 10x?"), with a configurable turn window and Markdown transcript export. No persistence across sessions, to avoid storing personal data (LGPD).
- **Interface (D6).** CLI only, with `rich` for formatting and `--debug` for observability. The focus of the challenge is the working agent.
- **Reference date (D9).** Real system date in production; `REFERENCE_DATE` only for tests and examples.

## Data handling and ambiguities

Full analysis in [DATA_ANALYSIS.md](DATA_ANALYSIS.md).

**Principle (D15): explicit limitation instead of interpretation.** Tools and domain code return, alongside the values, a list of `Limitation {code, message, source}`. Only rules without contradiction produce affirmative values; anything that depends on an unconfirmed reading appears as "to be confirmed" or is omitted with a limitation. The prompt requires the agent to pass limitations on without filling them in with assumptions.

**Data quality (Q1–Q12), summary:**

- Q1–Q2: products whose name diverges from the description (brand/model) or whose specifications diverge from the description (strings, keys, type). The loader detects and exposes the conflict without choosing a source of truth; the agent does not assert the conflicting fields. Detection is automatic by heuristic plus a manually reviewed list (products 135–137, 139, 140, 142–144).
- Q3 and Q7–Q8: historical order totals and payment methods diverge from current rules; the agent shows only the recorded total and never recalculates old orders.
- Q4–Q6: `coming_soon` or discontinued products appear with stock; a discontinued product is never offered (manual, 7.3) and `coming_soon` returns an availability limitation.
- Q9: orders "stuck" relative to the current date; the forecast is presented as an estimate, without claiming a delay.
- Q10: typo in the name of product 84 ("Cedr"); search is fuzzy-normalized and the displayed name is not changed.
- Q11–Q12: empty categories (wind, orchestral strings) and a catalog of 65 items against "more than 300" in the manual; the agent answers only from the system.

**Manual contradictions and gaps (P1–P16), summary:**

- Contacts (P1–P2): two WhatsApp numbers and two email spellings; both are given, with the source section, without claiming which is correct.
- Payment (P3, P4, P12): contradictory installment minimums (R$ 100, R$ 80, R$ 50); installments within the contradictory range come out as "to be confirmed". The 12x limit always applies, and combined payment only above R$ 2,000.00 (exactly R$ 2,000.00 returns a limitation).
- Shipping (P5, P8, P13): exactly R$ 500.00 and the municipalities of the metropolitan region are not defined in the manual; special shipping for "contrabaixos" and "pianos digitais" is passed on verbatim, without classifying the product.
- Withdrawal and exchanges (P6, P7, P9, P14): the purchase channel and the actual delivery date are not recorded, so there is no eligibility verdict; the agent exposes the rule, the available data and a limitation.
- Promotions and status (P11, P15, P16): price always comes from the CSV (`is_active`); more than one active promotion raises a limitation and none is chosen; `coming_soon` is not defined in the manual.
- P10: complaint registration and handoff, implemented as a local protocol number (T12).

## Known limitations

- **Inconsistent catalog data (Q1–Q12).** Products with conflicting information are shown only by their registered name, with a divergence warning.
- **Product conflicts not detected automatically beyond the reviewed list.** The heuristic covers brand, number of strings and number of keys; cases 136 and 143 are in a manual list. Subtle divergences (for example, a generic name with a specific model of the same brand, such as #138 and #141) are not flagged.
- **Manual contradictions handled as limitations (P1–P16).** The agent does not choose which phone, email or installment rule applies; it reports the divergence and points to confirmation with the team.
- **Holidays unknown.** Opening hours consider only the regular schedule; the manual does not list holidays, so the agent does not assert that the store is open on a holiday.
- **No shipping by postal code.** The manual has no postal-code table or list of metropolitan-region municipalities; outside Campo Grande the agent presents the rules and the limitation.
- **No return verdict.** Orders carry neither the purchase channel nor the real delivery date, so the agent does not say whether a return or exchange is eligible.
- **No persistence across sessions.** Each conversation lives in memory; only the optional transcript is written to disk.
- **No real WhatsApp channel.** CLI only; Streamlit and messaging integrations were not implemented.
- **Small, heuristic end-to-end scenarios.** There are 13 scenarios plus an emoji check, evaluated by presence of terms and tools called; the report needs manual review and the model varies between runs.
- **Groq free-tier quota.** The free tier allows 200k tokens per day (rolling 24-hour window) and 8k tokens per minute for `openai/gpt-oss-120b`; each model call costs about 2.4k tokens just for the prompt and tool schemas. The 4096-token cap and the per-minute limits make long answers and back-to-back runs slower (scenario runs need `--pause`), and the daily quota was exhausted during the T14 runs.
- **Scenarios 5, 9 and 10 not yet validated with the real model.** The fixes made after their failures are covered by automated tests with a fake LLM, but the final versions were not re-run against the real model because of the daily quota (see [End-to-end scenario results](#end-to-end-scenario-results)).
- **Emojis removed by code.** The prompt forbids emojis, but the model occasionally produced one, so `agent/output_guard.py` strips emojis (and normalizes typographic hyphens in phone numbers) from the final reply before it reaches the customer. This is covered by automated tests; confirmation with the real model is part of the pending runs.
- **Credentials.** The real-provider smoke tests, the scenarios and the example recordings depend on an API key. The code was first built and tested without a live key; the real runs came afterwards (T14).

## What I would do with more time

- Finish validating scenarios 5, 9 and 10 with the real model once the quota renews, and broaden the evaluation (more scenarios, more repetitions, judge-based grading).
- Resolve the P1–P16 contradictions with the team and then turn the limitations into rules.
- Add embeddings and a vector store if the manual grows.
- Optional conversation persistence with consent, a real WhatsApp channel and holidays from a calendar.
- Broader product-conflict detection with assisted review.

## Use of AI assistants

Tool: **Claude Code**. **Claude Opus 5.5** acted as coordinator and architect; **Claude Sonnet** agents carried out the tasks through **Orca**, in separate worktrees and branches, in the roles of implementation (Backend), AI/RAG and QA.

Workflow:

- **Planning approved before code.** The analysis of the data and the manual (`DATA_ANALYSIS.md`), the technical decisions (`TECHNICAL_DECISIONS.md`) and the architecture (`ARCHITECTURE.md`) were reviewed and approved before T01. The approval produced real adjustments: replacing "reasonable interpretations" with explicit limitations (D15), forbidding customer identification by name or email alone, and a persona without emojis.
- **Technical memory.** The repository is also an Obsidian vault; `CLAUDE.md` indexes the documents, and `docs/AGENT_GUIDE.md` tells each agent what to read and which rules are invariant (never change `data/`, do not invent rules, edit only the files in your request).
- **Contract per task.** Each task has acceptance criteria in `TASKS.md` and, since T05, a detailed contract (signatures, case table and literals) in `ARCHITECTURE.md` §5. This let implementation and tests be written in parallel and independently: in T05, the two versions agreed on the first run.
- **Review and integration by the coordinator.** One commit per task, after validating the criteria; green suite before integrating; SHA-256 hashes of `data/` checked after each task and unchanged. The record is in `docs/PROGRESS.md`.
- **Provider migration to Groq (T08b).** The user decided to use Groq as the LLM provider (D17). An AI/RAG agent wrote the new adapter behind the existing `LLMClient` interface and a QA agent wrote its tests, with no change to the agent, tools, domain or data. On integration, review found a script that captured `time.sleep` too early and test objects with overly strict validation; both were fixed.

Examples of problems caught by the process (from `docs/PROGRESS.md`):

- T07+T08: independent QA found that the `bad_request` message could leak API text, including the key; the AI/RAG agent fixed it.
- T06: the coordinator's review found four structural deviations in the PDF extraction (paragraphs and bold detected by regex), fixed by the agent; QA fixed one criterion and one false positive. Checking the criterion's feasibility against the real data before dispatching showed that pypdf kerning required comparing characters rather than words.
- T09+T10: QA fixed its own tests (exact category name, P15 with synthetic data, checking concepts in the prompt instead of exact phrases).
- T13: the Backend agent asked the coordinator (`ask`) before changing a T01 test, and the `--version` flag was approved.
- In T11+T12, 96 QA tests passed on first integration; in T13, 33.
- Real-model calibrations (T14, `docs/PROGRESS.md`): the first runs with Groq exposed problems that no fake-LLM test could show. Some failures were false negatives of the evaluator itself (a non-breaking hyphen U+2011 in a phone number, "20 %" written with a space, "consta que ele tem 88 teclas"); these were fixed in the evaluator and the stored answers were re-graded offline, without calling the API. Real agent defects were also found and fixed: the agent did not look up the order, answered a return question without consulting the policy, produced emojis despite the prompt (now removed by code), and invented a product after an empty search (an "unavailable" saxophone with non-existent alternatives), fixed with grounding rules in the tools and the prompt. The third run was invalid because of the daily quota.
- History rewrite before publication (T17 preparation): the challenge statement PDF was removed from versioning, and the user authorized rewriting the history to remove it from every commit before anything was published. Backup references and the reflog were purged, `git fsck` is clean, and all commit hashes cited in the documentation were updated.
- Usage-limit incident (T08b): the first attempt stopped at the account's 5-hour usage limit without producing anything (confirmed from the transcript). It was handled by stopping and abandoning the worker (`worker-stop`/`worker-abandon`) and re-dispatching with `--retry-of`.
- Recorded lessons: `send` only guarantees queuing, so contract changes must be confirmed in `worker_done`; files generated with `--check` need a `.gitattributes` with `eol=lf`.

## End-to-end scenario results

Real runs with Groq (`openai/gpt-oss-120b`, `LLM_EFFORT=low`, reference date `2026-03-25T10:00`) on 2026-11-01. Full details, per-run commits and the pending-test plan: [docs/E2E_RESULTS.md](docs/E2E_RESULTS.md). Real transcripts of runs 1 and 2: [docs/e2e/](docs/e2e/).

**Runs.**

| Run | Agent version | Raw result | Note |
|---|---|---|---|
| 1 | `60644c9` (before calibration) | 9/14 and 11/14 | first contact with the real model |
| 2 | `1a0779f` (calibration 1) | 11/14 and 9/14 | in repetition 2, five scenarios were interrupted by HTTP 429 (per-minute limit) |
| 3 | `4ac2216` (calibration 2) | 4/14, **invalid** | every failure was a 429 from the **daily** quota (200k tokens/day); the agent returned its technical-error fallback and no behavior was evaluated |

The answers from runs 1 and 2 were **re-graded offline** (no API call) with the corrected evaluator, to separate evaluator false negatives from real agent defects. Run 3 is not counted. The table below uses only the valid repetitions of runs 1 and 2, after that re-grading.

**Per scenario.**

| # | Scenario | Required | Valid repetitions | Status |
|---|---|---|---|---|
| 1 | Acoustic guitars up to R$ 1000 | | 4/4 OK | Passed |
| 2 | Store address | | 4/4 OK | Passed |
| 3 | Price of the Takamine GD20 | | 4/4 OK | Passed |
| 4 | Regret / return without an order number | | 4/4 OK | Passed |
| 5 | Return of order 4 with email | yes | 0/4 OK | **Pending — not yet validated with the real model.** Real defect (the agent did not look up the order, later did not consult the policy); fixes in `1a0779f` and `4ac2216`, the last one never run against the real model |
| 6 | Question about strings | | 4/4 OK | Passed |
| 7 | Out-of-scope question | | 4/4 OK | Passed |
| 8 | Ohana CK-20 on promotion | | 4/4 OK | Passed (the original failures were an evaluator false negative: "20 %") |
| 9 | Order 10 with the wrong phone | yes | 2/3 OK (1 interrupted by 429) | **Pending — not yet validated with the real model** (short confirmation of the final version). It failed once before fix `1a0779f` and passed after it |
| 10 | Saxophone, not in the catalog | | 0/3 OK (1 interrupted by 429) | **Pending — not yet validated with the real model.** Serious real defect (the model invented an "unavailable" saxophone and non-existent alternatives); fix in `4ac2216`, never run against the real model |
| 11 | Prompt injection | yes | 3/3 OK (1 interrupted by 429) | Passed |
| 12 | Korg Synth 1 Pro: number of keys | yes | 3/3 OK (1 interrupted by 429) | Passed (the original failure was an evaluator false negative) |
| 13 | Store WhatsApp | | 3/3 OK (1 interrupted by 429) | Passed (original false negative: non-breaking hyphen U+2011) |
| 14 | Replies without emojis | | 1 emoji in run 1 | Guaranteed by code since `1a0779f` (`agent/output_guard.py`, covered by automated tests); real-model confirmation goes with the pending runs |

Summary: scenarios 1-4, 6-8 and 11-13 passed; scenarios 5, 9 and 10 (and the real-model confirmation of 14) are **pending**. The passed scenarios were exercised with earlier prompt versions; later calibrations were targeted additions (order lookup, returns, empty searches). By the user's decision they will not be repeated without a reason.

**Why pending.** The Groq free-tier daily quota for `openai/gpt-oss-120b` (200k tokens/day, rolling 24-hour window) was exhausted on 2026-11-01. Commands to run once it renews (project root, `GROQ_API_KEY` in `.env`; details in [docs/E2E_RESULTS.md](docs/E2E_RESULTS.md), section 3):

```bash
python scripts/run_scenarios.py --only 5,10 --repeat 2 --pause 60 --report runtime/t14_prioridade_A.md   # ~40k tokens
python scripts/run_scenarios.py --only 9 --repeat 1 --pause 60 --report runtime/t14_prioridade_A3.md     # ~8k tokens
```

## Conversation examples

Example conversations are recorded with the real agent by `scripts/record_example.py` from scripts of customer messages in `examples/conversations/roteiros/`, using the same `Agent`, `Session` and Markdown export as the `/salvar` command. The agent's text is never edited, and nothing is written if any reply fails (no partial or fake transcripts). Contract: [ARCHITECTURE.md](ARCHITECTURE.md), section 5.9.2.

The three scripts:

1. `01_catalogo_violoes.txt` — catalog search for guitars up to R$ 1000, a follow-up and the PIX price.
2. `02_preco_promocao_frete.txt` — price, promotion and installments of the Ohana CK-20 ukulele, then shipping to Campo Grande.
3. `03_devolucao_pedido.txt` — a non-trivial return of order 4 (order data + policy + limitations).

```bash
python scripts/record_example.py --script examples/conversations/roteiros/01_catalogo_violoes.txt --out examples/conversations/01_catalogo_violoes.md
```

_Pending: the three real conversations will be recorded when the Groq daily quota renews (T15)._
