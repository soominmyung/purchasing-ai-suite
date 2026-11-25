# Quality checks

Every draft the pipeline writes is checked before the buyer sees it: the analysis, the purchase
request and the supplier email. Code checks what can be computed (format, items, figures,
citations); an LLM judge checks what needs reading (whether the history is reported faithfully,
whether a change is justified, whether a question leaks internal information). The definitions
are in `services/quality_checks.py`; the email validator is `check_email` in `services/agents.py`.

The same checks were used to choose the models (`docs/*_selection.md`).

See [pipeline inputs, responses and prompt safeguards](pipeline_io_and_checks.md)
for the data each model receives and the writing instructions that address every check.

## Severity and verdict

- **Blocking:** the draft must not be used as it is if this fails (invented or distorted history,
  a wrong figure, an item not in the input, internal information in a question for the supplier).
- **Warning:** usable, but a person should look.

A draft is **ready** only if every blocking check that applies passes; otherwise it **needs
review**. Warnings are listed but do not change the verdict. A check the judge could not answer
counts as not passed. Each check applies only when there is something to check (no proposed
change, no J3; no question for the supplier, no J5).

What happens on a failure:

| Draft | Blocking failure | Warning |
|---|---|---|
| Analysis | Sent back to the analysis agent with the reasons, up to two rewrites; if it still fails, the attempt with the fewest blocking failures is used and re-checked | Shown in the note at the top of the report and the purchase request |
| Purchase request | Shown in the note at the top of the draft (no rewrite) | Same |
| Supplier email | Sent back with the reason, up to two rewrites; a reason left after the last one is shown in the email's note | Shown in the email's note |

Every result, with its reason, also goes into the quality-check document kept for the operator.

## Analysis

The analysis agent returns a summary, numbered findings (facts from the history documents or the
stock figures, each with its source) and judgements that cite them: questions, proposed lead-time
and quantity changes, and recommended actions. Code works out the figures after a change.

### Code checks (C1–C10)

| ID | Passes when | Severity |
|---|---|---|
| C1 | The output parses and has every field with the right type | Blocking |
| C2 | Each code in the analysis JSON’s dedicated item fields appears in the input stock table’s `ItemCode` column. Code reads `items` in findings (including stock findings), questions, actions and lead-time changes, and `item_code` in quantity changes. For example, a question with `"items": ["200101"]` triggers a lookup of `200101` | Blocking |
| C3 | Each quantity change starts from the pipeline's suggested quantity | Blocking |
| C4 | Every finding rests on documents that were given and apply to what it is about, or on the stock position; every question, change and action cites at least one finding that exists and concerns its items or the supplier | Blocking |
| C5 | Each change is well formed and adds up: a lead time above 0 weeks, each item at most once, a quantity factor above 0 and not 1, the new quantity equal to the old one times the factor, rounded up | Blocking |
| C6 | Each item rated Critical after recalculation has an action listing its code and citing a stock finding for that code | Blocking |
| C7 | Each item rated Critical after recalculation has its name in the summary. Code ignores case, spaces and punctuation when matching | Warning |
| C8 | Splitting the summary on whitespace gives at most 100 words | Warning |
| C9 | Every number or date pair joined by an arrow in the prose matches a lead-time or quantity change pair | Blocking |
| C10 | Each item with a lead-time proposal has an entry in `figures_after_changes`, and its lead time, risk, gap and latest order date match the code's recalculation. Codes outside the lead-time proposals are flagged | Blocking |

### Judge checks (J1a–J8)

| ID | Passes when | Applies when | Severity |
|---|---|---|---|
| J1a | Every statement about supplier or item history is found in the documents given | Always | Blocking |
| J1b | No statement distorts what a document says (nothing made stronger, weaker or different) | Always | Blocking |
| J1c | No document's content is attributed to a supplier or item it does not name | Always | Blocking |
| J2a | If the history shows a supplier problem relevant to ordering, at least one question addresses it | A document concerns the supplier | Warning |
| J2b | If the history shows an item problem relevant to ordering, at least one question addresses it | A document names an item | Warning |
| J2c | No question presumes a problem the inputs do not show | Always | Warning |
| J3a | Each proposed change goes the way its cited findings point | A change is proposed | Blocking |
| J3b | The reason explains a change size supported by the cited findings, including whether supplier-wide and item-level lead-time reasons add up or describe the same change. If the findings give no size, the reason identifies a supported estimate to be confirmed | A change is proposed | Blocking |
| J3c | No item that a change's reason applies to is left without the change, unless the findings support it | A change is proposed | Blocking |
| J4 | Stock figures, dates and risk quoted in the summary, findings, questions, actions and change reasons match the item's figures after any changes. The check covers figures from stock data and code calculations | Always | Blocking |
| J5 | No question for the supplier reveals anything internal (stock levels, weeks to stockout, budget, the company's own analysis); asking what faster or partial delivery the supplier can offer passes | A question is marked for the supplier | Blocking |
| J6 | Each question and action follows from the findings it cites | Questions or actions exist | Warning |
| J7 | No document unused by any question, change or action describes an issue requiring one for this order | A document is unused by all three | Warning |
| J8 | Findings state facts only, with no judgement of what they mean for the order | Findings exist | Warning |

## Purchase request

The approval agent writes the Purpose and Justification; code writes the item table, the
timing and the signature block.

| ID | Passes when | By | Severity |
|---|---|---|---|
| P1a | Purpose and Justification add no new fact, risk or assessment. The judge accepts explanations of an input action backed by its findings, and a pre-order check stated as a condition | Judge | Warning |
| P1b | Figures are quoted as the input gives them, with no word that judges them | Judge | Warning |
| P1c | Where other words are used, the meaning does not change ("about 60%" is not "60%") | Judge | Warning |
| P2 | Purpose has 1–2 sentences, Justification 2–4 | Code | Warning |
| P3 | Only the history documents given are cited | Code | Blocking |

## Supplier email

The email agent writes only the requests; code adds the greeting, the purpose, the item lines and
the signature. The agent never receives stock figures, risk levels or internal questions.

| ID | Passes when | By | Severity |
|---|---|---|---|
| E1 | Code searches the requests for listed terms. The validator looks for internal stock quantities, time to stockout, risk assessments, or mention of internal analysis, review, logic or tools | Code, then `claude-haiku-5-5` | Blocking |
| E2 | No past problem of the supplier, or when it happened, is mentioned; a question about how a step of this order will proceed or be checked passes | `claude-haiku-5-5` | Blocking |
| E3 | Code searches for excluded item names and codes. The validator also checks for indirect references to excluded items | Code, then `claude-haiku-5-5` | Blocking |
| E4 | Requests cover the information this order needs from `points_to_clarify`, omitting questions about `other_items`. A question about the related step of this order can cover a past issue | Judge | Warning |
| E5 | No question is asked twice | Judge | Warning |
| E6 | For each item in `ask_earliest_dispatch`, the requests ask for its earliest dispatch or delivery sooner than the standard lead time | Judge | Warning |
| E7 | No purchase order is promised, the item list is not repeated, and it reads as a polite request to a business partner | Judge | Warning |

## The judge

`claude-haiku-5-5`, thinking at high effort, answering in the shape of a scoring sheet, one call
per draft (`judge_model`, `judge_effort` and `judge_output` in `config.py`). It is from a different model family from the
writers (`gpt-6.1-sol`), so no draft is judged by a model of its own family. Before use it was
validated on outputs with known faults and on hand-scored outputs (`docs/judge_selection.md`).
