# Koda Editorial Fact-Check Framework

## Purpose

Every Koda editorial article passes through this fact-checking pipeline before
publication. The goal: zero hallucinated stats, zero outdated data, zero
misattributed claims. Readers trust us because we verify.

---

## Pipeline Position

```
Draft Article (Step 03E)
       |
       v
Voice Review (Step 04E)
       |
       v
>>> FACT-CHECK GATE (Step 04F) <<<   <-- THIS DOCUMENT
       |
       v
Visuals (Step 05E)
       |
       v
Render & Publish (Step 06E)
```

Fact-checking runs AFTER voice review (so we check the final prose, not a draft
that will change) and BEFORE visuals (so we don't generate charts for claims
that get cut).

---

## Step 1: Claim Extraction

Scan the article and extract every verifiable claim into a structured list.

**What counts as a verifiable claim**:
- Any number (revenue, parameters, percentages, dates, prices, counts)
- Any attribution ("According to X," "X said," "X announced")
- Any causal statement ("X caused Y," "X led to Y," "because of X")
- Any comparison ("X outperforms Y," "X is faster than Y")
- Any temporal claim ("launched last week," "since 2024," "first ever")
- Any organizational claim (who leads what, who owns what, who partnered)

**What is NOT a verifiable claim** (skip these):
- Editorial opinions clearly marked as such ("I think," "The evidence suggests")
- Hypothetical scenarios ("If X happens, then Y")
- General industry knowledge that is definitional ("LLMs generate text")

**Output format**:
```
CLAIM #1: "Mistral Small 4 has 22 billion parameters"
  Type: Statistic
  Source in article: Section 3, paragraph 2
  Verification priority: HIGH (core thesis claim)

CLAIM #2: "Apache 2.0 license"
  Type: Factual/legal
  Source in article: Section 3, paragraph 3
  Verification priority: MEDIUM
```

---

## Step 2: Multi-Source Verification

Each claim is verified against independent sources. The number of required sources
depends on the claim type.

### Source Requirements by Claim Type

| Claim Type | Min Sources | Accepted Source Tiers |
|-----------|------------|---------------------|
| Statistics (revenue, params, benchmarks) | 2 independent | Tier 1 (official release, paper) + Tier 2 (established outlet) |
| Quotes / Attribution | 1 primary | Tier 1 only (original transcript, press release, official blog) |
| Company announcements | 1 primary + 1 secondary | Tier 1 (company blog/PR) + Tier 2 (news coverage) |
| Market data (prices, indices) | 1 real-time | Tier 1 (exchange data, Bloomberg, CoinGecko) |
| Causal / analytical claims | 2 supporting | Tier 1-2 (studies, analyses, expert commentary) |
| Historical / timeline | 1 authoritative | Tier 1-2 (Wikipedia acceptable for dates if corroborated) |
| Regulatory / legal | 1 primary | Tier 1 only (government source, court filing, official gazette) |

### Source Tier Definitions

**Tier 1 — Primary Sources** (highest trust):
- Official company blogs, press releases, SEC filings
- Peer-reviewed papers, arXiv preprints from named researchers
- Government databases, regulatory filings
- Direct quotes from verified interviews/transcripts
- Official documentation (model cards, API docs, release notes)

**Tier 2 — Established Reporting** (high trust):
- Reuters, AP, Bloomberg, Financial Times, Wall Street Journal
- The Verge, Ars Technica, TechCrunch, The Information
- Established AI-focused outlets (The Gradient, Import AI, Jack Clark)

**Tier 3 — Secondary Sources** (use with caution):
- Industry analyst reports (Gartner, IDC, CB Insights)
- Well-known newsletter authors (Packy McCormick, Ben Thompson)
- Named expert commentary on social media (verified accounts only)

**Never use as sole source**:
- Anonymous social media posts
- Reddit threads without corroboration
- AI-generated summaries from other tools
- Undated or unattributed blog posts
- Cached/archived content without checking current status

### Verification Methods

**For statistics and numbers**:
1. Search for the exact number in Perplexity/web search
2. Find the PRIMARY source (the company/researcher who produced it)
3. Check the date: is this current data or historical?
4. Verify units and scale (billions vs millions, parameters vs tokens)
5. If the number appears in fewer than 2 independent results: FLAG

**For quotes and attribution**:
1. Search for the exact quote string
2. Trace to original source (transcript, blog post, interview)
3. Verify the speaker is correctly identified
4. Check context: is the quote being used in the same spirit as the original?

**For company announcements**:
1. Find the official announcement (company blog, PR wire)
2. Cross-reference with at least one news outlet covering it
3. Check date: is this the most recent status? (announcements get superseded)

**For market data**:
1. Pull from real-time or same-day source
2. Specify the timestamp/date of the data point
3. Use closing prices, not intraday, unless the article specifically discusses intraday

---

## Step 3: Error Category Screening

After verification, scan for these four categories of errors that AI-generated
content is most prone to.

### 3A: Hallucinated Statistics

**Red flags**:
- Numbers that return 0 results in web search
- Suspiciously round figures without source (exactly 90%, exactly $1B)
- Statistics with no date qualifier ("75% of developers" — when? which survey?)
- Benchmark scores that don't match any published evaluation
- Revenue/valuation figures that conflict between sources

**Action**: If a stat can't be verified in 2+ sources, either:
- Replace with a verified alternative
- Remove the claim entirely
- Reframe as approximate: "reportedly around X" with source

### 3B: Outdated Data

**Red flags**:
- Leadership titles from >6 months ago (CEOs change, companies restructure)
- Pricing that may have changed (model API costs change frequently)
- Benchmark comparisons using old model versions
- Regulatory status that may have evolved
- Funding rounds that may have closed at different terms

**Action**: For any data point >3 months old:
- Check if an update exists
- If using older data, explicitly date it: "as of Q3 2025"
- For leadership: verify current role via LinkedIn or company page

### 3C: Attribution Errors

**Red flags**:
- Common names (multiple "John Smith" in tech)
- Paraphrased statements presented as direct quotes
- Claims attributed to a company when made by an individual (or vice versa)
- Research attributed to the wrong institution
- Model capabilities attributed to the wrong version

**Action**: Every attribution must trace to a specific source document.
If uncertain, use: "According to reports from [outlet]" rather than
direct attribution to a person.

### 3D: Conflated Events

**Red flags**:
- Two separate announcements merged into one narrative
- Timeline compression (events weeks apart presented as same-day)
- Geographic confusion (similar events in different countries)
- Version confusion (GPT-4 vs GPT-4o vs GPT-4 Turbo treated as same)
- Company confusion (OpenAI vs Open AI vs other "Open" companies)

**Action**: For each event referenced, verify:
- Exact date
- Exact entity involved
- That it is distinct from similar events

---

## Step 4: Confidence Scoring and Decision

After verification, assign an overall confidence score.

### Scoring

Each claim gets a confidence level:
- **VERIFIED** (95%+): 2+ independent Tier 1-2 sources confirm. Exact match.
- **HIGH CONFIDENCE** (80-94%): 1 Tier 1 source + logical consistency.
- **MODERATE** (60-79%): 1 Tier 2 source, or Tier 1 source with minor discrepancy.
- **LOW** (<60%): Cannot find independent confirmation. Single weak source.
- **DISPUTED**: Sources contradict each other.

### Decision Logic

```
IF all claims VERIFIED or HIGH CONFIDENCE:
  -> PUBLISH. Log the verification report.

IF any claim is MODERATE:
  -> REWRITE that claim. Options:
     a) Find better sources and upgrade to HIGH
     b) Hedge the language: "reportedly," "according to unconfirmed reports"
     c) Remove the claim if not essential to the thesis

IF any claim is LOW:
  -> REMOVE the claim. Do not publish unverified statistics or attributions.
     If the claim is central to the thesis, the article needs a different angle.

IF any claim is DISPUTED:
  -> ACKNOWLEDGE the dispute in the article:
     "Sources disagree on X. [Source A] reports Y, while [Source B] reports Z."
     This is actually good editorial practice and builds trust.
```

---

## Step 5: Transparency in Published Article

Every Koda editorial includes these trust signals:

### Inline Citations
- Major claims include parenthetical source references
- Format: "Mistral Small 4 shipped with 22B parameters (Mistral AI blog, March 2026)"
- Not every sentence needs a citation. Cite: statistics, quotes, announcements,
  and any claim a skeptical reader might question.

### Source Footer
At the bottom of every editorial, include a "Sources" section:
```
Sources: Mistral AI Official Blog, Reuters, The Verge, Perplexity Research,
Koda Daily Digest (March 29, 2026)
```

### Corrections Policy
- If a factual error is discovered post-publication, add a correction notice
  at the top of the article:
  "Correction (March 30, 2026): This article originally stated X. The correct
  figure is Y. We regret the error."
- Never silently edit published articles. Always note the correction.

---

## Practical Implementation in the Skill Pipeline

The fact-check step uses these tools in sequence:

```
1. CLAIM EXTRACTION
   Tool: Opus 4.6 (structured extraction from article text)
   Output: Numbered list of claims with types and priorities

2. PARALLEL VERIFICATION
   Tools (run simultaneously):
   - Perplexity search (perplexity_ask) for each HIGH priority claim
   - Web search for exact numbers/quotes
   - Firecrawl scrape on primary sources (company blogs, papers)

3. CONFIDENCE SCORING
   Tool: Opus 4.6 (compare article claims vs verification results)
   Output: Per-claim confidence + overall score

4. DECISION + REWRITE
   IF any claims fail: rewrite those sections
   IF all pass: proceed to visuals
```

**Time budget**: 3-5 minutes for a 1,500-word article (most time is in parallel
web searches). This is acceptable for a daily editorial that publishes in the morning.

---

## Common Pitfalls to Watch

1. **Model name/version confusion**: GPT-4, GPT-4o, GPT-4 Turbo, GPT-4.5,
   GPT-5, GPT-5.4 are ALL different. Always verify the exact version.

2. **Parameter count vs token count**: These are different numbers. A model
   with 22B parameters does not have 22B tokens.

3. **Open-source vs open-weight**: "Open-source" means code + weights + training
   data. "Open-weight" means weights only. Many models are open-weight, not
   truly open-source. Get this right.

4. **Funding rounds**: "Raised $X" vs "valued at $X" are very different claims.
   Verify which one.

5. **Benchmark scores**: Always cite which benchmark (MMLU, HumanEval, ARC-AGI,
   etc.) and which version. Scores are meaningless without the benchmark name.

6. **"According to" chains**: If Source A cites Source B who cites Source C,
   go to Source C. Don't cite Source A for Source C's claim.

7. **Temporal accuracy**: "Last week" in a newsletter from March 20 means
   March 13-19, not whatever week you're writing the editorial. Convert
   relative dates to absolute dates.
