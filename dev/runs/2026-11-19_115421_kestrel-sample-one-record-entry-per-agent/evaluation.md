# Analysis Quality Check

**Supplier:** KestrelComponents  
**Run id:** 2026-11-19_115421_kestrel-sample-one-record-entry-per-agent  
**Snapshot date:** 2025-04-05  
**Result:** Ready: all 16 blocking checks passed; no warnings.  
**Checked by:** code, and `claude-haiku-5-5` (effort high) for the judgement checks

## Attempts

| Attempt | Judge run | Blocking checks failed | Sent back for a rewrite |
| --- | --- | --- | --- |
| 1 | yes | none | no |

## Analysis Checks

| Check | Severity | Result | Reason |
| --- | --- | --- | --- |
| Output format (C1) | blocking | Pass | all required fields present |
| Items match the input (C2) | blocking | Pass | every item named is in the input |
| Figures match the input (C3) | blocking | Pass | changes start from the pipeline's figures |
| Every judgement cites findings that apply (C4) | blocking | Pass | every judgement cites findings that apply |
| Proposed changes well formed and add up (C5) | blocking | Pass | the changes are well formed and add up |
| Each Critical item has an action on its stock position (C6) | blocking | Pass | each Critical item has one |
| Summary names every Critical item (C7) | warning | Pass | names every Critical item |
| Summary within about 100 words (C8) | warning | Pass | 81 words |
| Arrows in the text match the proposed changes (C9) | blocking | Pass | every arrow matches a change |
| Figures after the lead-time changes follow the rules (C10) | blocking | Pass | the figures follow the rules |
| History statements found in the documents (J1a) | blocking | Pass | Finding 1 matches document [1] (four-week longer lead times from 1 April 2025, Gdansk move, lasting to end of 2025); finding 2 matches [2] (50% higher demand since January 2025, fleet contract to December 2027); finding 3 matches [3] (steady demand over the past year). |
| History not distorted (J1b) | blocking | Pass | Each history statement keeps the document's strength and scope: 'four weeks longer', '50% higher', 'steady over the past year', and the contract end date of December 2027 are all reported as stated. |
| History not attributed to what it does not name (J1c) | blocking | Pass | Finding 1 has items [] and covers all products, matching the supplier-wide document [1]; finding 2 is tied to 520003 GasketKit, which document [2] names; finding 3 is tied to 520005 OilSeal, which document [3] names. |
| No question presumes a problem the data does not show (J2c) | warning | Pass | Questions 1 and 2 concern BearingCap and ThrustWasher, which show stock gaps, and the plant move in document [1]. Question 3 asks about the GasketKit demand increase shown in [2]. No question presumes a supplier or item problem absent from the inputs. |
| Stock figures quoted match the input (J4) | blocking | Pass | Finding 4 gives 12 weeks, 10-week gap, 5 April 2025 (post-change 12, 10, 2025-04-05); finding 5 gives 20 weeks, two-week gap, 5 April 2025 (post-change 20, 2, 2025-04-05); finding 6 gives 22 weeks, no gap, 5 April 2025 (post-change 22, 0, 2025-04-05); finding 7 gives 24 weeks, no gap, 19 April 2025 (post-change 24, 0, 2025-04-19); action 1 gives 28 June 2025 (post-change 2025-06-28); action 2 gives 23 August 2025 (post-change 2025-08-23); summary gives longest gap 10 weeks and BearingCap/ThrustWasher as Critical (post-change Critical). |
| Each proposed change goes the way its findings point (J3a) | blocking | Pass | supplier_lead_time sets 22 weeks (18 plus the four-week extension in finding 1). lead_time_changes applies this to all seven items, and each revised latest order date falls between 1 April and 31 December 2025. |
| Each proposed change is the size its findings support (J3b) | blocking | Pass | The size of the change is +4 weeks (18 to 22), which matches the four-week figure in document [1]. No item-specific extra delay is added, and none is documented. |
| No item the same reason applies to is left out (J3c) | blocking | Pass | All seven items, 520001 to 520007, have lead_time_weeks 22 in both lead_time_changes and figures_after_changes, so no item is left at 18 weeks. |
| Questions marked for the supplier reveal nothing internal (J5) | blocking | Pass | Supplier-directed question 1 asks about expedited or partial deliveries and earliest firm dates for BearingCap and ThrustWasher, and question 2 asks about production allocation and committed dates. Neither reveals stock levels, weeks to stockout, budget or internal plans. |
| Each question and action follows from its findings (J6) | warning | Pass | Question 1 cites findings 4 and 5 (BearingCap and ThrustWasher gaps). Question 2 cites finding 1 (plant move). Question 3 cites finding 2 (GasketKit demand). Actions 1, 2 and 3 cite findings 4, 5 and 6 (gaps and cover). Action 4 cites finding 1 (allocations). Action 5 cites findings 2 and 7 (GasketKit demand and order date). Each follows from its cited finding. |
| No document with a problem for this order left unused (J7) | warning | Pass | Document [3] (OilSeal steady demand) is cited only by finding 3. No question, proposed change or action cites finding 3 or document [3]. |
| Findings state facts only (J8) | warning | Pass | Findings 1 to 7 state only dates, durations, percentages, stock-derived gaps and document content, with no judgement of what they mean for the order. |
| Supplier problem raised as a question (J2a) | warning | Pass | Document [1] describes a supplier-wide four-week lead-time increase that matters for ordering. Question 2 asks how the plant move will affect production allocation and committed delivery dates. |
| Item problem raised as a question (J2b) | warning | Pass | Document [2] describes a 50% GasketKit demand increase that matters for ordering. Question 3 asks whether the increase relates to the market and whether the fleet contract is already in the suggested quantity of 5200. Document [3] describes no problem. |

## Purchase Request Text

**Result:** Ready: all 1 blocking checks passed; no warnings.

| Check | Severity | Result | Reason |
| --- | --- | --- | --- |
| Purchase request adds nothing to its input (P1a) | warning | Pass | Every fact in the purpose and justification (overdue 5 April order date, 10-week and 2-week gaps, 18 to 22 week lead time change, Gdansk move, GasketKit 50% demand increase, the actions) traces to the input. No added conclusion about the supplier or the decision appears. |
| Purchase request quotes figures as given (P1b) | warning | Pass | Figures are quoted as given: '10 weeks and 2 weeks', '22-week lead time', '28 June 2025', '23 August 2025', '50%'. No judging word attaches to any figure. |
| Purchase request keeps the input's meaning (P1c) | warning | Pass | Reworded terms keep the input's meaning, e.g. 'monthly-delivery contract through December 2027' for 'monthly deliveries through December 2027', 'usable supply by 28 June 2025' for 'usable supply available by 28 June 2025', and 'expedited shipping, a partial delivery or alternative supply' matches the action wording. |
| Purchase request paragraphs within length (P2) | warning | Pass | within length |
| Purchase request cites only documents given (P3) | blocking | Pass | all cited documents given |

## Supplier Email

**Exposure check (E1-E3, the validator):** passed (1 draft).  
**Other checks (warnings):** 0 of 4 not passed.

| Check | Severity | Result | Reason |
| --- | --- | --- | --- |
| Email covers every point to clarify (E4) | warning | Pass | Point 1 (expedited or partial deliveries for BearingCap and ThrustWasher, earliest firm dates) is covered by "What expedited or partial deliveries can you offer for BearingCap and ThrustWasher, and what are the earliest firm delivery dates?" Point 2 (plant move and production allocation) is covered by "Could you also confirm how production will be allocated and delivery dates committed for the items listed above?" That wording does not name OilSeal, the other_items entry. |
| Email asks no question twice (E5) | warning | Pass | The three questions are distinct: availability, lead times and commercial terms; expedited or partial deliveries with earliest firm dates; and production allocation with committed delivery dates. None is repeated. |
| Email asks the earliest dispatch where needed (E6) | warning | Pass | "What expedited or partial deliveries can you offer for BearingCap and ThrustWasher, and what are the earliest firm delivery dates?" asks for both ask_earliest_dispatch items, BearingCap and ThrustWasher, to be delivered sooner than standard lead time. |
| Email promises no order and reads as a request (E7) | warning | Pass | The output makes no purchase order promise and does not write out the full item list; it refers to "the items listed above". It uses polite openers ("Could you please confirm", "Could you also confirm") in flowing sentences addressed to the supplier. The point used as written, "What expedited or partial deliveries can you offer...", is a direct but conversational question. |
