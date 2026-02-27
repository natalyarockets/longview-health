# Longview Health -- Future Roadmap

> Ideas and features beyond the MVP. Rough priority order within each section,
> but nothing here is committed -- it's a living document.

---

## Beyond Labs: Full Medical Document Coverage

The MVP extraction pipeline handles lab panels well. Next is broadening coverage
to the full spectrum of medical documents people actually accumulate.

- **Imaging reports** (MRI, CT, X-ray, ultrasound) -- extract findings, impressions,
  and any quantifiable measurements. These are typically narrative text with embedded
  values rather than tabular data, so the LLM extraction path handles them naturally.
  Need to ensure the region grouper handles the typical imaging report structure
  (indication, technique, findings, impression).

- **Pathology reports** -- biopsy results, cytology, histology. Often have both
  narrative findings and discrete values (margins, staging, grade).

- **Diagnostic studies** (EKG, EEG, pulmonary function, sleep studies) -- mix of
  waveform interpretations and numeric results.

- **Vitals and physical exam** -- blood pressure, heart rate, weight, BMI over time.
  Often buried in visit notes rather than standalone documents.

- **Medication lists and changes** -- track what was prescribed when, dosage changes,
  and the reasoning behind them.

---

## Health Journal: Context, Notes, and Qualitative Tracking

Numerical results without context are often meaningless. A creatinine value only
matters if you know the patient just ran a marathon, is dehydrated, or has been
dealing with kidney issues. The system needs to capture the human story alongside
the data.

### Scan context / intake notes

Before or during a scan, the user should be able to attach a quick note explaining
*why* they're adding these documents:

```
longview rescan natalya --note "Added new results -- been tracking weird stomach
pain for the past 3 weeks. GI ordered these after the ultrasound was inconclusive."
```

These notes get timestamped and associated with the scan session. They provide
the "why" that the documents themselves don't contain. When reviewing trends later,
you'd see not just that values changed but what was happening in the person's life
at that time.

### Health journal entries

Standalone journal entries that aren't tied to a document scan. Things like:

- Symptom tracking: "Stomach pain worse after eating, especially dairy"
- Lifestyle context: "Started new medication last Tuesday", "Training for marathon"
- Observations: "Energy levels much better since iron supplements"
- Provider notes: "Dr. Smith thinks this might be SIBO, ordered breath test"

```
longview journal natalya "Stomach pain seems to be improving since cutting out
gluten. Energy is better too. Follow-up with GI next week."
```

### Linking context to results

Journal entries and scan notes should appear in the trends report alongside the
numerical data. When you look at a trend line, you should be able to see what was
happening at each point in time -- not just the numbers, but the narrative.

---

## Investigation Tracking: Grouping by Health Issue

Medical records are organized by date and provider, but patients think in terms
of problems: "my back injury", "the thyroid thing", "whatever is causing these
headaches." The system should support this mental model.

### Issue-based grouping

Create named investigations or health issues that group related documents,
results, and journal entries together:

```
longview issue create natalya "Stomach pain investigation"
longview issue add natalya "Stomach pain investigation" --doc <doc-id>
longview issue add natalya "Stomach pain investigation" --result <result-id>
```

An issue collects:
- Related documents (the GI referral, the ultrasound, the blood work)
- Specific results (the ones that matter for this issue)
- Journal entries (symptom tracking, medication changes)
- A timeline view showing everything related to this issue chronologically

### Smart suggestions

Once issues exist, the system could suggest groupings:
- "These 3 new results look related to 'Stomach pain investigation' -- add them?"
- Cluster by ordering provider, related test names, or temporal proximity

### File organization

Users may want to organize their actual document files to reflect these groupings.
Options to explore:
- Subfolders within the vault's document directory (would need recursive enumeration)
- Filename prefixes or tags (e.g., renaming files to include the issue)
- Symlinks or aliases (keep originals, create grouped views)
- Pure metadata approach (grouping lives in the DB, files stay flat)

The right approach probably starts with pure metadata grouping in SQLite and
adds file organization as an optional convenience later.

---

## Trend Report Enhancements

- **Contextual annotations** -- show journal entries and scan notes on the trend
  timeline, not just numerical data points
- **Issue-filtered reports** -- export trends for a specific health issue, showing
  only the relevant results and context
- **Comparison view** -- overlay related tests (e.g., all liver function tests
  on one chart)
- **Flagging patterns** -- highlight when multiple related values are trending
  in the same direction (e.g., all kidney markers rising together)

---

## Other Ideas

- **Provider tracking** -- which doctor ordered what, contact info, specialties
- **Appointment prep** -- generate a summary of recent changes to bring to a visit
- **Family health patterns** -- cross-vault queries for hereditary trend spotting
  (opt-in, privacy-first)
- **Document OCR quality scoring** -- flag documents that may have been poorly
  scanned and suggest re-scanning
- **Backup/export** -- export entire vault as portable archive (SQLite + documents)
