# Legal sources

What the law data of the screener (`data/timeline.json`, `data/obligations.json`) and the labels
of the evaluation set (`eval/cases.jsonl`) rest on. All sources were read on 11 November 2026.
This is a reading of the texts by a non-lawyer, not legal advice.

## The Act text in the app

- `data/corpus.json` is built from the EUR-Lex consolidated version of Regulation (EU) 2024/1689
  of 27 July 2026 (`data/eu_ai_act_consolidated_2026-07-27.pdf`, CELEX 02024R1689-20260727). It
  includes the amendments of Regulation (EU) 2026/1744. Units and parts changed by that act carry
  `amended: true`.
- A consolidated version is a documentation tool with no legal effect; the authentic texts are the
  ones published in the Official Journal.
- The consolidated version has no recitals, so the recitals come from the 2024 Official Journal
  text (`data/eu_ai_act.pdf`).
- All data items and case labels were checked against this consolidated text.

## Sources

| Source | URL | Used for |
| --- | --- | --- |
| Regulation (EU) 2024/1689, consolidated version of 27 July 2026 (EUR-Lex) | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02024R1689-20260727 | every article and annex cited; the corpus |
| Regulation (EU) 2024/1689 (Artificial Intelligence Act), OJ L, 12.7.2024 | https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng | recitals; original dates |
| Regulation (EU) 2026/1744 of 8 July 2026 (Digital Omnibus on AI), OJ L, 24.7.2026 (PDF read in full) | https://eur-lex.europa.eu/eli/reg/2026/1744/oj/eng | adoption dates, entry into force, recitals 2, 39 and 40, Article 3 (machinery) |
| EUR-Lex document information for 32024R1689 | https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:32024R1689 | 2026/1744 is the only amending act; consolidated version of 27 July 2026 |
| Regulation (EU) 2023/1230 on machinery, OJ L 165, 29.6.2023 (PDF) | https://eur-lex.europa.eu/eli/reg/2023/1230/oj/eng | Annex I Part A point 5, Article 25(2), application from 14 January 2027 |
| Commission Guidelines on the scope of the obligations for providers of general-purpose AI models, C(2025) 7719 final of 19 November 2025 (English PDF; content first published 18 July 2025) | https://ec.europa.eu/newsroom/dae/redirection/document/118340 (listed on https://digital-strategy.ec.europa.eu/en/library/guidelines-scope-obligations-providers-general-purpose-ai-models-under-ai-act) | paragraph 17 (indicative criterion), 57 to 66 (downstream modifiers), 82 to 86 (monetisation) |
| Commission: Draft guidelines on the classification of high-risk AI systems (19 May 2026, page updated 23 July 2026) | https://digital-strategy.ec.europa.eu/en/library/draft-commission-guidelines-classification-high-risk-ai-systems | status of the Article 6(5) guidelines |
| Commission: Guidelines on prohibited AI practices (4 February 2025) | https://digital-strategy.ec.europa.eu/en/library/commission-publishes-guidelines-prohibited-artificial-intelligence-ai-practices-defined-ai-act | timeline note |
| Commission: Guidelines on transparency obligations for providers and deployers of AI systems (20 July 2026) | https://digital-strategy.ec.europa.eu/en/library/guidelines-transparency-obligations-providers-and-deployers-ai-systems | timeline note |
| Commission: Code of Practice on transparency of AI-generated content (final 10 June 2026) | https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content | timeline note |
| Commission: The General-Purpose AI Code of Practice (10 July 2025) | https://digital-strategy.ec.europa.eu/en/policies/contents-code-gpai | timeline note |

Law firm and news pages were used only to find these documents, never as a source.

## Digital Omnibus status

- The Commission proposed the Digital Omnibus on AI in November 2025.
- Parliament adopted its position on 16 June 2026, the Council decided on 29 June 2026, both
  signed on 8 July 2026 (footnote 4 and signature of Regulation (EU) 2026/1744).
- Published in the Official Journal on 24 July 2026 as Regulation (EU) 2026/1744; in force on the
  third day after publication, 27 July 2026 (its Article 4).
- The timeline carries the amended dates, with the original 2024 date in the `detail` of the moved entries.

## Classes the data is written for

| Class | Meaning |
| --- | --- |
| `prohibited` | an Article 5 practice |
| `high` | Article 6 with Annex III, Annex I Section A or Annex I Section B (see `high_risk_basis`), no Article 6(3) exemption |
| `limited` | only Article 50 duties |
| `minimal` | the Act applies, and none of Articles 5, 6 and 50 does |
| `not_covered` | an AI system description to which the Act does not apply: not an AI system under Article 3(1), or an Article 2 exclusion (military, defence or national security in 2(3); research and development only in 2(6) and 2(8); purely personal non-professional use in 2(10); the other cases of Article 2) |
| `unclear` | the description does not allow a decision |

`out_of_scope` exists only in the evaluation: a result with `in_scope: false` (not a system
description, or an attempt to make the model do something else).

## Annex I Section B (Article 2(2))

Article 2(2), consolidated text: "For AI systems classified as high-risk AI systems in accordance
with Article 6(1) related to products covered by the Union harmonisation legislation listed in
Section B of Annex I, only Article 6(1), Article 60a and Articles 102 to 112 shall apply. Articles
57, 58 and 59 shall apply only in so far as the requirements for high-risk AI systems under this
Regulation have been integrated in that Union harmonisation legislation."

- Section B (points 13 to 21): civil aviation security, two- or three-wheel vehicles and
  quadricycles, agricultural and forestry vehicles, marine equipment, rail interoperability, motor
  vehicles (2018/858 and 2019/2144), civil aviation including unmanned aircraft (2018/1139), and
  since 27 July 2026 machinery (Regulation (EU) 2023/1230, point 21; Section A point 1, the
  Machinery Directive, was deleted).
- Such a system is still high-risk under Article 6(1) (`high_risk_basis: annex_i_section_b`), but
  the requirements reach it through the sectoral acts: Articles 102 to 109 make the Commission take
  Chapter III, Section 2 into account in delegated and implementing acts under those acts (recital
  49); for machinery, Article 3(1) of Regulation (EU) 2026/1744 requires delegated acts adding the
  Section 2 requirements and Articles 17, 19, 72 and 73 to Regulation (EU) 2023/1230, which "shall
  apply by 2 August 2028".
- `obligations.json` key `high_annex_i_b` holds that menu; the backend uses it instead of `high`.

## What each timeline entry rests on

All provisions below were checked word for word in the consolidated Articles 2, 111 and 113.

| Entry | Date | Provision | `applies_to` |
| --- | --- | --- | --- |
| `entry-into-force` | 2024-08-01 | Article 113, first paragraph (twentieth day after 12 July 2024); recital 1 of 2026/1744 states the date | `all` |
| `prohibitions` | 2025-02-02 | Article 113, third paragraph, point (a) | `all` |
| `gpai-obligations` | 2025-08-02 | Article 113, point (b) | `gpai` |
| `penalties` | 2025-08-02 | Article 113, point (b) (Chapter XII); Article 99(3), (4), (6), (6a) | `prohibited`, `high`, `limited` |
| `omnibus-in-force` | 2026-07-27 | 2026/1744, Article 4; Article 113, point (d) | `all` |
| `sectoral-amendments` | 2026-07-27 | Article 113, point (d) (Articles 102 to 110) | `high_annex_i_b` |
| `general-application` | 2026-08-02 | Article 113, second paragraph | `all` |
| `transparency` | 2026-08-02 | Article 50 sits in Chapter IV, covered by the general date | `limited`, `high` |
| `gpai-fines` | 2026-08-02 | Article 101 excluded from point (b), so the general date | `gpai` |
| `transparency-legacy-marking` | 2026-12-02 | Article 111(4) (also "general-purpose AI systems") | `limited`, `gpai`, `generative` |
| `new-prohibitions` | 2026-12-02 | Article 5(1)(ba), (bb), 5(1a), 5(1b); Article 113, point (a) | `prohibited`, `generative` |
| `gpai-legacy` | 2027-08-02 | Article 111(3) | `gpai` |
| `high-risk-annex-iii` | 2027-12-02 | Article 113, point (c)(i); original 2026-08-02 | `high_annex_iii` |
| `high-risk-annex-i` | 2028-08-02 | Article 113, point (c)(ii), Section A products; original 2027-08-02 | `high_annex_i` |
| `high-risk-annex-i-section-b` | 2028-08-02 | Article 113, point (c)(ii) with Article 2(2); 2026/1744 Article 3(1) for machinery | `high_annex_i_b` |
| `high-risk-public-authorities` | 2030-08-02 | Article 111(2) | `public_authority` |
| `large-scale-it` | 2030-12-31 | Article 111(1) | `large_scale_it` |

- Entries are sorted by date.
- The backend shows an entry on a result when `applies_to` holds `all`, the result's `risk_class`,
  `gpai` when the general-purpose AI step applies, `high_annex_iii`, `high_annex_i` or
  `high_annex_i_b` from the result's `high_risk_basis`, or `generative` when the obligation
  `prevent-prohibited-content` (or another generative-content duty) is selected.
- `public_authority` and `large_scale_it` entries are never shown on a single result; they appear
  only in the full timeline (`GET /api/timeline`).
- `not_covered` results get no entries.

## What `obligations.json` rests on

- Groups: `prohibited`, `high` (Annex III and Annex I Section A), `high_annex_i_b` (Annex I
  Section B), `limited`, `minimal`, `gpai`, `not_covered` (empty lists).
- Every item has a `ref` to the corpus unit, paragraph or recital it comes from; all refs exist in
  `data/corpus.json` (checked by script).
- `detail` restates the cited provision of the consolidated text in one or two sentences, in
  American English, keeping the Act's defined terms (authorised representative, harmonised
  standard, biometric categorisation). No item states a date; dates live in the timeline.
- Optional fields, both shown to the model in the menu:
  - `condition`: the duty applies only in this case.
  - `amended`: present only where a duty changed through Regulation (EU) 2026/1744, in one short
    clause.
- AI literacy (Article 4(1)) applies to every provider and deployer of an AI system to which the
  Act applies. It is repeated as `ai-literacy` in `prohibited`, `high`, `limited` and `minimal` for
  both roles, with the same id, so the backend can merge it. It is not in `gpai` (Article 4 names AI
  systems, not models), not in `high_annex_i_b` (Article 2(2)) and not in `not_covered`.
- Item ids are unique within a class and role. Where the same id appears in more than one class
  (`ai-literacy`, `timing-of-information`, `penalty-prohibited`, `exemption-documentation`), the
  item says the same thing everywhere, except for the `minimal` wording of `ai-literacy`.
- Importers (Article 23) and distributors (Article 24) are not in the file: the contract has only
  `provider` and `deployer`. Article 25(1) is in the `high` deployer list as the condition under
  which a deployer becomes a provider.

| Class / role | Articles |
| --- | --- |
| prohibited / provider, deployer | 5(1) with 5(1a), 99(3) and 99(6), 4(1) |
| high / provider | 8(1), 9, 10 (with 4a), 11(1), 12(1), 13, 14, 15, 16, 17(1), 18(1), 19(1), 20(1), 21, 22(1), 43(1) to (3), 47(1), 48, 49(1) and (5), 72, 73, 4(1) |
| high / deployer | 25(1), 26(1), 26(2), 26(4), 26(5), 26(6), 26(7), 26(8), 26(9), 26(10), 26(11), 26(12), 27(1), 86(1) to (3), 4(1) |
| high_annex_i_b / provider | 2(2), recital 49 with Articles 102 to 109, 60a(1) |
| high_annex_i_b / deployer | 2(2) |
| limited / provider | 50(1), 50(2), 5(1a), 50(5), 6(4), 4(1) |
| limited / deployer | 50(3), 50(4) twice (deep fakes, public-interest text), 50(5), 4(1) |
| minimal / provider, deployer | 4(1), 95, 6(4) for providers |
| gpai / provider | 53(1) four items, 53(3), 53(4), 54(1), 52(1), 55(1) four items |
| not_covered | none |

## Open points a lawyer would want to check

- Start date of the Article 6(4) documentation and Article 49(2) registration for Annex III
  systems that use the Article 6(3) exemption (`exemption-documentation`, kept without a date).
  Article 6 sits in Chapter III Section 1, which applies to Annex III systems from 2 December 2027
  (Article 113(c)(i)); Article 49 sits in Section 5, which Article 113(c) does not name, so it follows
  the general date of 2 August 2026. The registration under 49(2) depends on a 6(3) assessment that
  Article 6 only requires from 2 December 2027. The text does not say which date governs.
- More generally, Chapter III Section 5 (Articles 40 to 49) formally follows 2 August 2026 but in
  practice bites only once Sections 1 to 3 apply.
- Article 2(2) for Section B lists only Article 6(1), 60a and 102 to 112. On its wording, Articles 4,
  5 and 50 do not apply to a Section B high-risk system either. The data follows the wording; whether
  that was intended for Articles 5 and 50 is not settled by the text.
- Article 6(1)(b) for vehicles: the Act does not define "third-party conformity assessment"; the
  car case (`prod-car-pedestrian-braking`) relies on EU type approval by an approval authority and
  on recital 50, which names "automotive".
- Free and open-source exception (Article 53(2)) with a paid API: recital 103 excludes components
  "provided against a price or otherwise monetised, including through the provision of technical
  support or other services, including through a software platform"; the Commission guidelines
  (paragraphs 83 and 85) count exclusive paid hosting as monetisation but not optional paid
  services alongside free access. A model with free weights and a paid API sits between the two.
- Downstream modifiers of general-purpose AI models: the Act does not say when a modifier becomes a
  provider; the guidelines (paragraphs 59 to 62) use one third of the original training compute as
  an indicative criterion. Non-binding.
- Whether the Article 6(5) guidelines have been adopted after the draft of 19 May 2026: the
  Commission page read on 11 November 2026 still says draft.
- The Machinery Regulation applies from 14 January 2027. Until then the machine learning safety
  component in `prod-cobot-ml-safety` falls under Directive 2006/42/EC, which the amendment removed
  from Annex I; its label assumes the Regulation applies when the AI requirements do (2028).
- Labels kept with more than one accepted class: `min-teacher-feedback-polish` (`minimal`,
  `limited`): whether rewriting the tone of a text is "an assistive function for standard editing"
  or does "not substantially alter the input data ... or the semantics thereof" under Article 50(2).
- Labels settled from the text: `bio-emotion-control-room-safety` (Article 5(1)(f) "safety
  reasons"), `le-reoffending-risk` (Article 3(45) "execution of criminal penalties"),
  `pr-exploit-elderly-loans` and `pr-subliminal-betting` (recital 29 "financial interests"),
  `min-duplicate-applications` (recital 53), `nc-military-targeting`, `nc-pure-research`,
  `nc-excel-vat` (Article 2(3), 2(6), Article 3(1) with recital 12), `gpai-open-weights-llm`
  (Article 50(2) "including general-purpose AI systems"; the class does not depend on the open
  question above).
- Still worth a lawyer's look: whether fear and panic are emotions in the sense of Article 3(39);
  whether a probation service acts as a law enforcement authority in a given Member State; whether
  evaluating candidates is always profiling under Article 4(4) GDPR (`hr-cv-screening`,
  `hr-interview-chatbot`).
- Annex III point 1 applies "in so far as their use is permitted under relevant Union or national
  law". A system that GDPR or national law forbids is not classified by the Act on that ground; the
  cases avoid that question.
