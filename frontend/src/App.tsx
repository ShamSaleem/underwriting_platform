import { useEffect, useRef, useState } from "react";
import { api, CaseSummary, ChecklistGroup, Decision, DecisionCode, Stats, UploadResult } from "./api";

/* ------------------------------------------------------------------ helpers */
function pillClass(code: DecisionCode): string {
  if (code === "PREF") return "ok";
  if (code === "STD") return "std";
  if (code === "DECL") return "bad";
  if (code === "POST" || code === "REFER") return "refer";
  return "rate"; // R25/R50/R100/RATED/FE/EXCL
}

// Badge label: show the exact loading for a generic RATED so it never reads as a phantom code.
function decisionLabel(code: DecisionCode, ratingPct: number): string {
  if (code === "RATED") return `RATED +${ratingPct}%`;
  return code;
}
const money = (n: number) =>
  "$" + Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
const lines = (s: string) =>
  s.split("\n").map((x) => x.trim()).filter(Boolean);
// Capitalise the first letter of each word (after spaces, hyphens, slashes) for dropdown labels.
const titleCase = (s: string) => s.replace(/(^|[\s/-])(\w)/g, (_, sep, ch) => sep + ch.toUpperCase());

/* ------------------------------------------------------------- DecisionView */
function DecisionView({ d }: { d: Decision }) {
  return (
    <div>
      <div className="verdict">
        <span className={"badge " + pillClass(d.overall_decision)}>{decisionLabel(d.overall_decision, d.total_rating_pct)}</span>
        <div>
          <div style={{ fontWeight: 700, fontSize: 17 }}>{d.applicant}</div>
          <div className="muted" style={{ fontSize: 13 }}>
            {d.product.replace(/_/g, " ")} · sum assured {money(d.sum_assured)}
          </div>
        </div>
      </div>

      <div className="chips">
        <span className="chip">Rating <b>+{d.total_rating_pct}%</b></span>
        {d.flat_extra_per_mille > 0 && (
          <span className="chip">Flat extra <b>{d.flat_extra_per_mille}‰</b></span>
        )}
        <span className="chip">Evidence <b>{d.evidence_required.join(", ")}</b></span>
        <span className="chip">Assessment <b>{d.llm_used ? "rules + AI" : "rules-only"}</b></span>
        {d.requires_referral && <span className="chip" style={{ color: "var(--blue)" }}>⚑ Referral required</span>}
      </div>

      {d.referral_reasons.length > 0 && (
        <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
          <b>Referral:</b> {d.referral_reasons.join("; ")}
        </div>
      )}
      {d.exclusions.length > 0 && (
        <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
          <b>Exclusions:</b> {d.exclusions.join("; ")}
        </div>
      )}

      <table>
        <thead>
          <tr><th>Risk factor</th><th>Decision</th><th>Assessment &amp; manual citation</th></tr>
        </thead>
        <tbody>
          {d.findings.map((f, i) => (
            <tr key={i} style={{ cursor: "default" }}>
              <td>{f.factor}</td>
              <td>
                <span className={"pill " + pillClass(f.decision_code)}>
                  {f.decision_code}{f.rating_pct ? ` +${f.rating_pct}%` : ""}
                </span>
              </td>
              <td>
                {f.assessment}
                <div style={{ marginTop: 4, display: "flex", gap: 8, alignItems: "center" }}>
                  <span className="muted" style={{ fontSize: 12 }}>{f.article}</span>
                  <span className={"src-tag " + (f.source === "llm" ? "llm" : "")}>{f.source}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="explain">{d.explanation}</div>
    </div>
  );
}

/* --------------------------------------------------------------- Dashboard */
function Dashboard({ go }: { go: (id: string) => void }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
    api.cases().then(setCases).catch(() => {});
  }, []);

  return (
    <div>
      <div className="grid kpis">
        <Kpi label="Cases assessed" value={String(stats?.total_cases ?? "—")} />
        <Kpi label="Acceptance rate" value={stats ? stats.acceptance_rate + "%" : "—"} gold />
        <Kpi label="Avg. rating" value={stats ? "+" + stats.avg_rating_pct + "%" : "—"} />
        <Kpi label="Total sum assured" value={stats ? money(stats.total_sum_assured) : "—"} />
      </div>

      <div className="section-title">Decision distribution</div>
      <div className="card">
        {stats && Object.keys(stats.by_decision).length ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            {Object.entries(stats.by_decision).map(([code, n]) => (
              <span key={code} className={"pill " + pillClass(code as DecisionCode)}>
                {code} · {n}
              </span>
            ))}
            <span className="chip">⚑ Referrals · {stats.referrals}</span>
          </div>
        ) : (
          <div className="muted">No cases yet — run an assessment to populate the portfolio.</div>
        )}
      </div>

      <div className="section-title">Recent cases</div>
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <CaseTable cases={cases.slice(0, 8)} go={go} />
      </div>
    </div>
  );
}

function Kpi({ label, value, gold }: { label: string; value: string; gold?: boolean }) {
  return (
    <div className="card kpi">
      <div className="label">{label}</div>
      <div className={"value" + (gold ? " gold" : "")}>{value}</div>
      <div className="delta">live portfolio</div>
    </div>
  );
}

function CaseTable({ cases, go }: { cases: CaseSummary[]; go: (id: string) => void }) {
  if (!cases.length) return <div className="empty">No cases recorded yet.</div>;
  return (
    <table>
      <thead>
        <tr><th>Reference</th><th>Applicant</th><th>Type</th><th>Sum assured</th><th>Decision</th><th>When</th></tr>
      </thead>
      <tbody>
        {cases.map((c) => (
          <tr key={c.id} onClick={() => go(c.id)}>
            <td className="mono muted">{c.id}</td>
            <td>{c.applicant}</td>
            <td className="muted">{c.applicant_type}</td>
            <td className="mono">{money(c.sum_assured)}</td>
            <td>
              <span className={"pill " + pillClass(c.decision)}>
                {c.decision}{c.rating_pct ? ` +${c.rating_pct}%` : ""}
              </span>
            </td>
            <td className="muted mono" style={{ fontSize: 12 }}>{c.created_at.replace("T", " ").replace("+00:00", "Z")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ---------------------------------------------------------------- Wizard */
const SAMPLES: Record<string, any> = {
  Clean: {
    applicant_type: "individual", product: "individual_life", sum_assured: 300000,
    annual_income: 80000, existing_life_cover: 0, assets: "", liabilities: "",
    full_name: "Aisha Bello", age: 34, sex: "female", smoking: "non_smoker", alcohol: "none",
    occupation: "software engineer", occupation_class: 1,
    height_cm: 165, weight_kg: 60, hba1c: "", fasting_glucose: "", systolic_bp: "", diastolic_bp: "",
    avocations: "", foreign_travel: "", family_history: "", disclosures_list: [],
  },
  Diabetic: {
    applicant_type: "individual", product: "individual_life", sum_assured: 750000,
    annual_income: 90000, existing_life_cover: 200000, assets: 300000, liabilities: 120000,
    full_name: "John Carter", age: 47, sex: "male", smoking: "occasional", alcohol: "moderate",
    occupation: "warehouse supervisor", occupation_class: 4,
    height_cm: 178, weight_kg: 104, hba1c: 7.4, fasting_glucose: "", systolic_bp: 148, diastolic_bp: 92,
    avocations: "recreational scuba diving to 30m, ~10 dives/year",
    foreign_travel: "quarterly trips to Nigeria",
    family_history: "father had a heart attack at 55",
    disclosures_list: [
      { condition: "Diabetes", details: "Type 2, diagnosed 4 years ago, on metformin, no complications", age_at_diagnosis: 43, treated: true },
    ],
  },
  GroupClean: {
    applicant_type: "group", product: "group_life", sum_assured: 100000,
    annual_income: 250000, existing_life_cover: 0, assets: "", liabilities: "",
    company_name: "Northwind Software", industry: "Information technology", num_employees: 120,
    average_age: 34, occupation_classes: "1, 2", free_cover_limit_requested: 100000,
    notes: "Office-based workforce, low occupational risk, stable headcount.",
  },
  GroupComplex: {
    applicant_type: "group", product: "group_life", sum_assured: 500000,
    annual_income: 1800000, existing_life_cover: 0, assets: "", liabilities: "",
    company_name: "Atlas Mining & Construction", industry: "Mining and construction", num_employees: 45,
    average_age: 49, occupation_classes: "4, 5, 6", free_cover_limit_requested: 500000,
    notes: "High-hazard occupations, small scheme, older workforce and a free-cover limit well above the no-evidence threshold.",
  },
};

type Step = { id: string; title: string; sub: string };
const STEPS_INDIVIDUAL: Step[] = [
  { id: "applicant", title: "Applicant", sub: "Art. 1" },
  { id: "documents", title: "Documents", sub: "Art. 3·4·16" },
  { id: "financial", title: "Financial", sub: "Art. 3" },
  { id: "build", title: "Build & vitals", sub: "Art. 5·6·7" },
  { id: "lifestyle", title: "Lifestyle", sub: "Art. 11–14" },
  { id: "history", title: "History", sub: "Art. 8·10·15" },
  { id: "review", title: "Review", sub: "Art. 17·19" },
];
const STEPS_GROUP: Step[] = [
  { id: "applicant", title: "Company", sub: "Art. 1" },
  { id: "documents", title: "Documents", sub: "Art. 3·16" },
  { id: "group", title: "Group risk", sub: "Art. 11·16" },
  { id: "review", title: "Review", sub: "Art. 17" },
];

const DISCLOSURE_CATEGORIES = ["Cardiovascular", "Diabetes", "Cancer", "Respiratory", "Mental health", "Other"];

// Article 11 occupational risk classes — name shown alongside the 1–6 class number.
const OCCUPATION_CLASSES: [number, string][] = [
  [1, "Office workers"],
  [2, "Teachers"],
  [3, "Sales professionals"],
  [4, "Factory workers"],
  [5, "Construction workers"],
  [6, "Mining / offshore"],
];

function bmiOf(h: any, w: any): number | null {
  const H = Number(h), W = Number(w);
  if (!H || !W) return null;
  const m = H / 100;
  return Math.round((W / (m * m)) * 10) / 10;
}

function Wizard({ onSaved, go }: { onSaved: () => void; go: (id: string) => void }) {
  const [f, setF] = useState<any>(SAMPLES.Diabetic);
  const [picked, setPicked] = useState(false);
  const [bulk, setBulk] = useState(false);
  const [step, setStep] = useState(0);
  const [checks, setChecks] = useState<Set<string>>(new Set());
  const [reqGroups, setReqGroups] = useState<ChecklistGroup[]>([]);
  const [reqBusy, setReqBusy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Decision | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const set = (k: string, v: any) => setF((p: any) => ({ ...p, [k]: v }));
  const isGroup = f.applicant_type === "group";
  const steps = isGroup ? STEPS_GROUP : STEPS_INDIVIDUAL;
  const current = steps[Math.min(step, steps.length - 1)];

  function switchType(t: string) {
    setF((p: any) => ({ ...p, applicant_type: t, product: t === "group" ? "group_life" : "individual_life" }));
    setStep(0); setChecks(new Set()); setReqGroups([]); setResult(null); setErr(null);
  }

  // Pick the applicant type from the entry cards, then drop into that type's wizard.
  function choose(t: string) {
    switchType(t);
    setPicked(true);
  }

  // Pull the manual-driven documentation checklist when the documents step opens.
  useEffect(() => {
    if (current.id !== "documents") return;
    setReqBusy(true);
    api.requirements({ applicant_type: f.applicant_type, sum_assured: Number(f.sum_assured) || 0, annual_income: Number(f.annual_income) || 0 })
      .then((r) => setReqGroups(r.groups))
      .catch(() => setReqGroups([]))
      .finally(() => setReqBusy(false));
  }, [current.id, f.applicant_type, f.sum_assured, f.annual_income]);

  const toggle = (k: string) =>
    setChecks((prev) => { const n = new Set(prev); n.has(k) ? n.delete(k) : n.add(k); return n; });

  const requiredKeys = reqGroups.flatMap((g) => g.items.filter((i) => i.required).map((i) => i.key));
  const docsComplete = requiredKeys.length > 0 && requiredKeys.every((k) => checks.has(k));

  function canAdvance(): boolean {
    switch (current.id) {
      case "applicant":
        if (Number(f.sum_assured) <= 0) return false;
        return isGroup ? !!(f.company_name && Number(f.num_employees) > 0) : !!(f.full_name && Number(f.age) > 0);
      case "documents":
        return !reqBusy && docsComplete;
      default:
        return true;
    }
  }

  function buildBody() {
    const num = (v: any) => (v === "" || v == null ? undefined : Number(v));
    const base: any = {
      applicant_type: f.applicant_type,
      product: f.product,
      sum_assured: Number(f.sum_assured),
      financials: {
        annual_income: Number(f.annual_income || 0),
        existing_life_cover: Number(f.existing_life_cover || 0),
        assets: num(f.assets),
        liabilities: num(f.liabilities),
      },
    };
    if (isGroup) {
      base.group = {
        company_name: f.company_name || "Unnamed Co",
        industry: f.industry || "",
        num_employees: Number(f.num_employees || 1),
        average_age: num(f.average_age),
        occupation_classes: lines(String(f.occupation_classes || "")).flatMap((x) => x.split(",")).map((x) => Number(x.trim())).filter((n) => !isNaN(n)),
        free_cover_limit_requested: num(f.free_cover_limit_requested),
        notes: f.notes || null,
      };
    } else {
      base.individual = {
        full_name: f.full_name || "Applicant",
        age: Number(f.age || 0),
        sex: f.sex || "other",
        smoking: f.smoking || "non_smoker",
        alcohol: f.alcohol || "none",
        occupation: f.occupation || "",
        occupation_class: num(f.occupation_class),
        avocations: lines(String(f.avocations || "")),
        foreign_travel: lines(String(f.foreign_travel || "")),
        family_history: lines(String(f.family_history || "")),
        medical_disclosures: (f.disclosures_list || [])
          .filter((d: any) => (d.condition || "").trim())
          .map((d: any) => ({
            condition: d.condition.trim(),
            details: (d.details || "").trim() || null,
            age_at_diagnosis: num(d.age_at_diagnosis),
            treated: d.treated == null ? null : !!d.treated,
          })),
        metrics: {
          height_cm: num(f.height_cm), weight_kg: num(f.weight_kg),
          hba1c: num(f.hba1c), fasting_glucose: num(f.fasting_glucose),
          systolic_bp: num(f.systolic_bp), diastolic_bp: num(f.diastolic_bp),
        },
      };
    }
    return base;
  }

  async function submit() {
    setBusy(true); setErr(null);
    try {
      const r = await api.underwrite(buildBody());
      setResult(r.decision);
      onSaved();
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  function restart() {
    setResult(null); setPicked(false); setStep(0); setChecks(new Set()); setReqGroups([]); setErr(null);
  }

  // ----- disclosure list helpers -----
  const addDisc = (cat: string) =>
    set("disclosures_list", [...(f.disclosures_list || []), { condition: cat === "Other" ? "" : cat, details: "", age_at_diagnosis: "", treated: null }]);
  const updDisc = (i: number, k: string, v: any) =>
    setF((p: any) => { const l = [...(p.disclosures_list || [])]; l[i] = { ...l[i], [k]: v }; return { ...p, disclosures_list: l }; });
  const rmDisc = (i: number) =>
    setF((p: any) => { const l = [...(p.disclosures_list || [])]; l.splice(i, 1); return { ...p, disclosures_list: l }; });

  /* ---- decision screen (after submit) ---- */
  if (result) {
    return (
      <div className="card wizard">
        <div className="docs-banner ok" style={{ marginBottom: 20 }}>✓ Assessment complete and saved to the case history.</div>
        <DecisionView d={result} />
        <div className="wizard-foot">
          <span className="muted" style={{ fontSize: 13 }}>{f.full_name || f.company_name}</span>
          <button className="btn primary" onClick={restart}>Start new assessment →</button>
        </div>
      </div>
    );
  }

  /* ---- bulk assessment opened from the entry card ---- */
  if (bulk) {
    return (
      <div>
        <button className="btn ghost" onClick={() => setBulk(false)} style={{ marginBottom: 16 }}>← Back to assessment types</button>
        <Batch go={go} onDone={onSaved} />
      </div>
    );
  }

  /* ---- entry cards: choose the applicant type before the form opens ---- */
  if (!picked) {
    return (
      <div className="type-pick">
        <div className="type-card">
          <div className="tc-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="8" r="3.6" />
              <path d="M5 20c0-3.7 3.1-6.2 7-6.2s7 2.5 7 6.2" />
            </svg>
          </div>
          <h3>Individual</h3>
          <p className="muted">Assess a single life against the manual — financials, build &amp; vitals, lifestyle, and medical history.</p>
          <ul className="tc-meta">
            <li>7-step guided wizard</li>
            <li>Build, vitals &amp; disclosures</li>
            <li>Articles 1–19</li>
          </ul>
          <button className="btn primary" onClick={() => choose("individual")}>Start individual assessment →</button>
        </div>
        <div className="type-card">
          <div className="tc-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
              <rect x="5.5" y="3.5" width="13" height="17" rx="1.5" />
              <path d="M9 7.5h2M13 7.5h2M9 11h2M13 11h2M9 14.5h2M13 14.5h2" />
              <path d="M10.5 20.5v-3h3v3" />
            </svg>
          </div>
          <h3>Group / Company</h3>
          <p className="muted">Assess an employer scheme — workforce profile, occupation classes, and free-cover limits.</p>
          <ul className="tc-meta">
            <li>4-step guided wizard</li>
            <li>Scheme &amp; occupational risk</li>
            <li>Articles 1·3·11·16·17</li>
          </ul>
          <button className="btn primary" onClick={() => choose("group")}>Start company assessment →</button>
        </div>
        <div className="type-card">
          <div className="tc-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 14.5V4" />
              <path d="M8 8l4-4 4 4" />
              <path d="M5 14.5v4a1.5 1.5 0 0 0 1.5 1.5h11a1.5 1.5 0 0 0 1.5-1.5v-4" />
            </svg>
          </div>
          <h3>Bulk from Excel</h3>
          <p className="muted">Assess many applicants at once — upload an .xlsx with one applicant per row, single person or hundreds.</p>
          <ul className="tc-meta">
            <li>Individuals &amp; groups in one sheet</li>
            <li>Worked-example template</li>
            <li>Per-row decisions &amp; errors</li>
          </ul>
          <button className="btn primary" onClick={() => setBulk(true)}>Start bulk assessment →</button>
        </div>
      </div>
    );
  }

  return (
    <div className="assess-layout">
      <div className="card wizard">
        {/* chosen type lives above the stepper; sample shortcuts moved to the aside */}
        <div className="toolbar" style={{ marginBottom: 20 }}>
          <button className="btn ghost" onClick={() => setPicked(false)}>← Change type</button>
          <span className="type-tag">{isGroup ? "Group / Company" : "Individual"}</span>
        </div>

        <Stepper steps={steps} step={step} onJump={(i) => i < step && setStep(i)} />

        <div className="step-head">
          <h3>{current.title}</h3>
          <div className="muted">{stepBlurb(current.id)}</div>
        </div>

        <div className="wizard-body">{renderStep()}</div>

        <div className="wizard-foot">
          <button className="btn ghost" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>← Back</button>
          <div className="toolbar">
            {err && <span style={{ color: "var(--red)", fontSize: 13 }}>{err}</span>}
            {current.id === "review" ? (
              <button className="btn primary" onClick={submit} disabled={busy}>
                {busy ? <span className="spinner" /> : "Assess eligibility →"}
              </button>
            ) : (
              <button className="btn primary" onClick={() => setStep((s) => s + 1)} disabled={!canAdvance()}>Next →</button>
            )}
          </div>
        </div>
      </div>

      <AssessAside
        f={f}
        isGroup={isGroup}
        current={current}
        step={step}
        steps={steps}
        showSamples={current.id === "applicant"}
        onSampleClean={() => { setF(isGroup ? SAMPLES.GroupClean : SAMPLES.Clean); setChecks(new Set()); }}
        onSampleComplex={() => { setF(isGroup ? SAMPLES.GroupComplex : SAMPLES.Diabetic); setChecks(new Set()); }}
      />
    </div>
  );

  /* ---------------- per-step rendering ---------------- */
  function renderStep() {
    switch (current.id) {
      case "applicant":
        return isGroup ? (
          <div className="form-grid">
            <Field label="Product">
              <select value={f.product} onChange={(e) => set("product", e.target.value)}>
                {["group_life", "medical", "credit_life"].map((p) => <option key={p} value={p}>{titleCase(p.replace(/_/g, " "))}</option>)}
              </select>
            </Field>
            <Field label="Sum assured / scheme benefit (USD)"><input type="number" value={f.sum_assured} onChange={(e) => set("sum_assured", e.target.value)} /></Field>
            <Field label="Company name"><input value={f.company_name || ""} onChange={(e) => set("company_name", e.target.value)} /></Field>
            <Field label="Industry"><input value={f.industry || ""} onChange={(e) => set("industry", e.target.value)} /></Field>
            <Field label="Number of employees"><input type="number" value={f.num_employees || ""} onChange={(e) => set("num_employees", e.target.value)} /></Field>
          </div>
        ) : (
          <div className="form-grid">
            <Field label="Product">
              <select value={f.product} onChange={(e) => set("product", e.target.value)}>
                {["individual_life", "critical_illness", "disability_income", "medical", "credit_life"].map((p) => <option key={p} value={p}>{titleCase(p.replace(/_/g, " "))}</option>)}
              </select>
            </Field>
            <Field label="Sum assured (USD)"><input type="number" value={f.sum_assured} onChange={(e) => set("sum_assured", e.target.value)} /></Field>
            <Field label="Full name"><input value={f.full_name} onChange={(e) => set("full_name", e.target.value)} /></Field>
            <Field label="Age"><input type="number" value={f.age} onChange={(e) => set("age", e.target.value)} /></Field>
            <Field label="Sex">
              <select value={f.sex} onChange={(e) => set("sex", e.target.value)}>
                <option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
              </select>
            </Field>
          </div>
        );

      case "documents":
        return (
          <div>
            <div className={"docs-banner" + (docsComplete ? " ok" : "")}>
              {reqBusy ? "Loading documentation requirements…"
                : docsComplete ? "✓ All mandatory documents accounted for — you may proceed."
                : "Tick each mandatory document once it is on file. The case cannot advance until all required items are checked."}
            </div>
            {reqGroups.map((g) => (
              <div key={g.title} className="check-group">
                <div className="cg-head">
                  <h4>{g.title}</h4>
                  <span className="cg-art">{g.article}</span>
                  {g.note && <span className="cg-note">{g.note}</span>}
                </div>
                {g.items.map((it) => (
                  <div key={it.key} className={"check-item" + (checks.has(it.key) ? " on" : "")} onClick={() => toggle(it.key)}>
                    <span className="box">{checks.has(it.key) ? "✓" : ""}</span>
                    <span className="lbl">{it.label}</span>
                    <span className={it.required ? "req" : "opt"}>{it.required ? "Required" : "Optional"}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        );

      case "financial": {
        const nw = (Number(f.assets) || 0) - (Number(f.liabilities) || 0);
        const hasNw = (f.assets !== "" && f.assets != null) || (f.liabilities !== "" && f.liabilities != null);
        return (
          <div className="form-grid">
            <Field label="Annual income (USD)"><input type="number" value={f.annual_income} onChange={(e) => set("annual_income", e.target.value)} /></Field>
            <Field label="Existing life cover in force (USD)"><input type="number" value={f.existing_life_cover} onChange={(e) => set("existing_life_cover", e.target.value)} /></Field>
            <Field label="Total assets (USD) — Article 3.4"><input type="number" value={f.assets || ""} onChange={(e) => set("assets", e.target.value)} /></Field>
            <Field label="Total liabilities (USD) — Article 3.4"><input type="number" value={f.liabilities || ""} onChange={(e) => set("liabilities", e.target.value)} /></Field>
            <Field label="Net worth (auto)"><input value={hasNw ? money(nw) : "—"} readOnly /></Field>
            <div className="field full">
              <div className="docs-banner">Article 3 caps cover at 15×–25× income by band; net worth (assets − liabilities) can justify additional cover. Cover above the combined limit is referred for financial justification.</div>
            </div>
          </div>
        );
      }

      case "build":
        return (
          <div className="form-grid">
            <Field label="Height (cm)"><input type="number" value={f.height_cm} onChange={(e) => set("height_cm", e.target.value)} /></Field>
            <Field label="Weight (kg)"><input type="number" value={f.weight_kg} onChange={(e) => set("weight_kg", e.target.value)} /></Field>
            <Field label="BMI (auto)"><input value={bmiOf(f.height_cm, f.weight_kg) ?? "—"} readOnly /></Field>
            <Field label="HbA1c (%) — Article 7"><input type="number" value={f.hba1c} onChange={(e) => set("hba1c", e.target.value)} /></Field>
            <Field label="Fasting glucose (mg/dL) — Article 7"><input type="number" placeholder="used if no HbA1c" value={f.fasting_glucose} onChange={(e) => set("fasting_glucose", e.target.value)} /></Field>
            <Field label="Blood pressure (sys / dia) — Article 6">
              <div style={{ display: "flex", gap: 8 }}>
                <input type="number" placeholder="sys" value={f.systolic_bp} onChange={(e) => set("systolic_bp", e.target.value)} />
                <input type="number" placeholder="dia" value={f.diastolic_bp} onChange={(e) => set("diastolic_bp", e.target.value)} />
              </div>
            </Field>
          </div>
        );

      case "lifestyle":
        return (
          <div className="form-grid">
            <Field label="Smoking — Article 14">
              <select value={f.smoking} onChange={(e) => set("smoking", e.target.value)}>
                <option value="non_smoker">Non-Smoker</option><option value="occasional">Occasional</option><option value="regular">Regular</option>
              </select>
            </Field>
            <Field label="Alcohol — Article 14">
              <select value={f.alcohol} onChange={(e) => set("alcohol", e.target.value)}>
                <option value="none">None / Minimal</option><option value="moderate">Moderate</option><option value="heavy">Heavy</option>
              </select>
            </Field>
            <Field label="Occupation"><input value={f.occupation} onChange={(e) => set("occupation", e.target.value)} /></Field>
            <Field label="Occupation class — Article 11">
              <select value={f.occupation_class ?? ""} onChange={(e) => set("occupation_class", e.target.value === "" ? "" : Number(e.target.value))}>
                <option value="">— Select Class —</option>
                {OCCUPATION_CLASSES.map(([n, label]) => <option key={n} value={n}>{n} — {titleCase(label)}</option>)}
              </select>
            </Field>
            <Field label="Avocations, one per line — Article 12" full><textarea value={f.avocations} onChange={(e) => set("avocations", e.target.value)} /></Field>
            <Field label="Foreign travel / residency, one per line — Article 13" full><textarea value={f.foreign_travel} onChange={(e) => set("foreign_travel", e.target.value)} /></Field>
          </div>
        );

      case "history":
        return (
          <div>
            <Field label="Family history, one per line — Article 15" full><textarea value={f.family_history} onChange={(e) => set("family_history", e.target.value)} /></Field>
            <div className="section-title" style={{ marginTop: 24 }}>Medical disclosures — Articles 6–10</div>
            {(f.disclosures_list || []).length === 0 && <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>No conditions disclosed. Add any that apply.</div>}
            {(f.disclosures_list || []).map((d: any, i: number) => (
              <div key={i} className="disc-row">
                <div className="disc-grid">
                  <Field label="Condition"><input value={d.condition} onChange={(e) => updDisc(i, "condition", e.target.value)} /></Field>
                  <Field label="Age at dx"><input type="number" value={d.age_at_diagnosis} onChange={(e) => updDisc(i, "age_at_diagnosis", e.target.value)} /></Field>
                  <Field label="Treated">
                    <select value={d.treated == null ? "" : d.treated ? "yes" : "no"} onChange={(e) => updDisc(i, "treated", e.target.value === "" ? null : e.target.value === "yes")}>
                      <option value="">—</option><option value="yes">Yes</option><option value="no">No</option>
                    </select>
                  </Field>
                  <button className="btn ghost" onClick={() => rmDisc(i)} title="Remove">✕</button>
                </div>
                <Field label="Details" full><textarea value={d.details} onChange={(e) => updDisc(i, "details", e.target.value)} /></Field>
              </div>
            ))}
            <div className="toolbar" style={{ marginTop: 8 }}>
              {DISCLOSURE_CATEGORIES.map((c) => <button key={c} className="btn ghost" onClick={() => addDisc(c)}>+ {c}</button>)}
            </div>
          </div>
        );

      case "group":
        return (
          <div className="form-grid">
            <Field label="Average age"><input type="number" value={f.average_age || ""} onChange={(e) => set("average_age", e.target.value)} /></Field>
            <Field label="Occupation classes (comma separated) — Article 11"><input value={f.occupation_classes || ""} onChange={(e) => set("occupation_classes", e.target.value)} /></Field>
            <Field label="Free cover limit requested (USD) — Article 16"><input type="number" value={f.free_cover_limit_requested || ""} onChange={(e) => set("free_cover_limit_requested", e.target.value)} /></Field>
            <Field label="Annual scheme premium / income (USD)"><input type="number" value={f.annual_income} onChange={(e) => set("annual_income", e.target.value)} /></Field>
            <Field label="Notes" full><textarea value={f.notes || ""} onChange={(e) => set("notes", e.target.value)} /></Field>
          </div>
        );

      case "review":
        return <ReviewSummary f={f} isGroup={isGroup} docsCount={checks.size} />;

      default:
        return null;
    }
  }
}

function stepBlurb(id: string): string {
  return {
    applicant: "Who and what is being assessed.",
    documents: "Evidence the manual mandates before this case can be underwritten.",
    financial: "Income and in-force cover for the Article 3 multiple check.",
    build: "Build and vitals — the numeric medical thresholds.",
    lifestyle: "Smoking, occupation, avocations and travel.",
    history: "Family history and disclosed conditions.",
    group: "Scheme risk profile.",
    review: "Confirm the inputs, then run the engine.",
  }[id] || "";
}

// Longer, manual-grounded context for the side rail — complements (doesn't repeat) the inline blurb.
function stepGuide(id: string): string {
  return {
    applicant: "Identity, product and the requested sum assured anchor every downstream check. The sum assured drives the financial-justification and evidence thresholds.",
    documents: "The required checklist is generated from the sum assured and income. All mandatory items must be on file before the case can advance.",
    financial: "Cover is capped at a 15×–25× income multiple by band; net worth can justify more. Anything above the combined limit is referred.",
    build: "BMI, blood pressure and HbA1c / fasting glucose are matched against the Article 5–7 tables to derive a build and metabolic rating.",
    lifestyle: "Smoking, occupation class, avocations and travel each carry their own loadings under Articles 11–14.",
    history: "Family history and any disclosed conditions are rated against Articles 6–10 and 15, and may trigger additional evidence.",
    group: "Workforce size, average age, occupation classes and the free-cover limit determine the scheme rating and referral threshold.",
    review: "Confirm every input below is correct. The engine combines all factors into one decision with cited articles.",
  }[id] || "";
}

function AssessAside({ f, isGroup, current, step, steps, showSamples, onSampleClean, onSampleComplex }: { f: any; isGroup: boolean; current: Step; step: number; steps: Step[]; showSamples: boolean; onSampleClean: () => void; onSampleComplex: () => void }) {
  const name = isGroup ? (f.company_name || "—") : (f.full_name || "—");
  return (
    <aside className="assess-aside">
      <div className="card aside-card">
        <div className="aside-title">Case summary</div>
        <dl className="aside-list">
          <div><dt>Type</dt><dd>{isGroup ? "Group / Company" : "Individual"}</dd></div>
          <div><dt>{isGroup ? "Company" : "Applicant"}</dt><dd>{name}</dd></div>
          <div><dt>Product</dt><dd>{String(f.product).replace(/_/g, " ")}</dd></div>
          <div><dt>Sum assured</dt><dd>{Number(f.sum_assured) > 0 ? money(f.sum_assured) : "—"}</dd></div>
          {isGroup
            ? <div><dt>Employees</dt><dd>{f.num_employees || "—"}</dd></div>
            : <div><dt>Age / sex</dt><dd>{f.age ? `${f.age} · ${f.sex}` : "—"}</dd></div>}
        </dl>
      </div>
      <div className="card aside-card">
        <div className="aside-title">Step {step + 1} of {steps.length} · {current.sub}</div>
        <div className="aside-step">{current.title}</div>
        <p className="aside-help">{stepGuide(current.id)}</p>
      </div>
      {showSamples && (
        <div className="card aside-card aside-samples">
          <div className="aside-title">Load sample</div>
          <div className="aside-sample-btns">
            <button className="btn ghost" onClick={onSampleClean}>Sample: clean</button>
            <button className="btn ghost" onClick={onSampleComplex}>Sample: complex</button>
          </div>
        </div>
      )}
    </aside>
  );
}

function Stepper({ steps, step, onJump }: { steps: Step[]; step: number; onJump: (i: number) => void }) {
  return (
    <div className="stepper">
      {steps.map((s, i) => {
        const state = i < step ? "done" : i === step ? "current" : "";
        return (
          <div key={s.id} className={"step " + state} onClick={() => onJump(i)} style={{ cursor: i < step ? "pointer" : "default" }}>
            <span className="dot">{i < step ? "✓" : i + 1}</span>
            <span className="step-label">{s.title}</span>
            <span className="step-sub">{s.sub}</span>
          </div>
        );
      })}
    </div>
  );
}

function ReviewSummary({ f, isGroup, docsCount }: { f: any; isGroup: boolean; docsCount: number }) {
  const rows: [string, any][] = isGroup
    ? [
        ["Company", f.company_name], ["Industry", f.industry || "—"], ["Product", String(f.product).replace(/_/g, " ")],
        ["Sum assured", money(f.sum_assured)], ["Employees", f.num_employees || "—"], ["Average age", f.average_age || "—"],
        ["Occupation classes", f.occupation_classes || "—"], ["Free cover limit", f.free_cover_limit_requested ? money(f.free_cover_limit_requested) : "—"],
        ["Documents on file", docsCount],
      ]
    : [
        ["Applicant", f.full_name], ["Age / sex", `${f.age} · ${f.sex}`], ["Product", String(f.product).replace(/_/g, " ")],
        ["Sum assured", money(f.sum_assured)], ["Annual income", money(f.annual_income)], ["Existing cover", money(f.existing_life_cover)],
        ["Net worth", (f.assets !== "" && f.assets != null) || (f.liabilities !== "" && f.liabilities != null) ? money((Number(f.assets) || 0) - (Number(f.liabilities) || 0)) : "—"],
        ["Smoking / alcohol", `${f.smoking} / ${f.alcohol}`], ["Occupation", `${f.occupation || "—"} (class ${f.occupation_class || "—"})`],
        ["BMI", bmiOf(f.height_cm, f.weight_kg) ?? "—"], ["HbA1c / fasting", `${f.hba1c || "—"} / ${f.fasting_glucose || "—"}`], ["Blood pressure", `${f.systolic_bp || "—"}/${f.diastolic_bp || "—"}`],
        ["Disclosures", (f.disclosures_list || []).length], ["Documents on file", docsCount],
      ];
  return (
    <div className="review-grid">
      {rows.map(([k, v]) => (
        <div key={k} style={{ borderBottom: "1px solid var(--border)", padding: "8px 0" }}>
          <div className="rk">{k}</div>
          <div className="rv">{String(v)}</div>
        </div>
      ))}
    </div>
  );
}

function Field({ label, children, full }: { label: string; children: any; full?: boolean }) {
  return (
    <div className={"field" + (full ? " full" : "")}>
      <label>{label}</label>
      {children}
    </div>
  );
}

/* ---------------------------------------------------------------- Cases */
function Cases({ go }: { go: (id: string) => void }) {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  useEffect(() => { api.cases().then(setCases).catch(() => {}); }, []);
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <CaseTable cases={cases} go={go} />
    </div>
  );
}

function CaseDetail({ id, back }: { id: string; back: () => void }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => { api.case(id).then(setData).catch(() => {}); }, [id]);
  return (
    <div>
      <button className="btn ghost" onClick={back} style={{ marginBottom: 16 }}>← Back</button>
      {!data ? <div className="empty">Loading…</div> : (
        <div className="card"><DecisionView d={data.decision_detail} /></div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- Batch / Excel */
function Batch({ go, onDone }: { go: (id: string) => void; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<UploadResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function upload() {
    if (!file) return;
    setBusy(true); setErr(null); setRes(null);
    try {
      const r = await api.uploadExcel(file);
      setRes(r);
      onDone();
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="card">
        <div className="section-title" style={{ marginTop: 0 }}>Bulk assessment from Excel</div>
        <p className="muted" style={{ marginTop: 0, fontSize: 14 }}>
          Upload an .xlsx with one applicant per row (single person or hundreds). Start from the
          template — it has the columns and worked examples. List fields use <b>;</b> separators;
          disclosures use <b>condition | details</b>.
        </p>
        <div className="toolbar">
          <a className="btn" href="/api/template">⬇ Download template</a>
          <label className="btn">
            {file ? file.name : "Choose .xlsx file"}
            <input
              type="file"
              accept=".xlsx"
              style={{ display: "none" }}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <button className="btn primary" onClick={upload} disabled={!file || busy}>
            {busy ? <span className="spinner" /> : "Upload & assess →"}
          </button>
          {err && <span style={{ color: "var(--red)", fontSize: 13 }}>{err}</span>}
        </div>
      </div>

      {res && (
        <>
          <div className="chips" style={{ marginTop: 20 }}>
            <span className="chip">Total <b>{res.total}</b></span>
            <span className="chip" style={{ color: "var(--green)" }}>Assessed <b>{res.succeeded}</b></span>
            {res.failed > 0 && <span className="chip" style={{ color: "var(--red)" }}>Errors <b>{res.failed}</b></span>}
          </div>
          <div className="card flush" style={{ marginTop: 8 }}>
            <table>
              <thead>
                <tr><th>Row</th><th>Applicant</th><th>Decision</th><th>Result</th></tr>
              </thead>
              <tbody>
                {res.results.map((r) => (
                  <tr key={r.row} onClick={() => r.id && go(r.id)} style={{ cursor: r.id ? "pointer" : "default" }}>
                    <td className="mono muted">{r.row}</td>
                    <td>{r.decision?.applicant ?? "—"}</td>
                    <td>
                      {r.ok && r.decision ? (
                        <span className={"pill " + pillClass(r.decision.overall_decision)}>
                          {decisionLabel(r.decision.overall_decision, r.decision.total_rating_pct)}
                        </span>
                      ) : (
                        <span className="pill bad">ERROR</span>
                      )}
                    </td>
                    <td className="muted" style={{ fontSize: 13 }}>
                      {r.ok
                        ? (r.decision?.requires_referral ? "⚑ referral required" : "auto-decided")
                        : r.error}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- Login */
function Login({ onLogin }: { onLogin: (user: string) => void }) {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const r = await api.login(u.trim(), p);
      onLogin(r.user);
    } catch {
      setErr("Invalid username or password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card card" onSubmit={submit}>
        <div className="login-brand">
          <div className="logo">UW</div>
          <div>
            <div className="name">Underwriting Engine</div>
            <div className="tag">Life &amp; Health Eligibility</div>
          </div>
        </div>
        <h2>Sign in to your account</h2>
        <div className="field">
          <label>Username</label>
          <input value={u} onChange={(e) => setU(e.target.value)} autoFocus autoComplete="username" />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" />
        </div>
        {err && <div className="login-err">{err}</div>}
        <button className="btn primary" type="submit" disabled={busy} style={{ width: "100%", justifyContent: "center", marginTop: 4 }}>
          {busy ? <span className="spinner" /> : "Sign in"}
        </button>
        <div className="login-hint">Demo access — <b>admin</b> / <b>aegis2024</b></div>
      </form>
    </div>
  );
}

/* ---------------------------------------------------------------- App */
type View = { name: "dashboard" | "assess" | "cases" } | { name: "case"; id: string };

// Toggle the `dark` class on <html> and persist. Mirrors etimad's colour-mode store.
function useColorMode(): [boolean, () => void] {
  const [dark, setDark] = useState<boolean>(() => localStorage.getItem("uw_theme") === "dark");
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("uw_theme", dark ? "dark" : "light");
  }, [dark]);
  return [dark, () => setDark((d) => !d)];
}

export default function App() {
  const [user, setUser] = useState<string | null>(() => localStorage.getItem("aegis_user"));
  const [view, setView] = useState<View>({ name: "dashboard" });
  const [tick, setTick] = useState(0); // refresh dashboard after a save
  const [collapsed, setCollapsed] = useState<boolean>(() => localStorage.getItem("uw_sidebar") === "collapsed");
  const [dark, toggleDark] = useColorMode();

  const nav = (n: "dashboard" | "assess" | "cases") => setView({ name: n });
  const openCase = (id: string) => setView({ name: "case", id });
  const logout = () => { localStorage.removeItem("aegis_user"); setUser(null); };
  const toggleSidebar = () =>
    setCollapsed((c) => { localStorage.setItem("uw_sidebar", c ? "expanded" : "collapsed"); return !c; });

  if (!user) {
    return (
      <Login
        onLogin={(u) => { localStorage.setItem("aegis_user", u); setUser(u); }}
      />
    );
  }

  const titles: Record<string, [string, string]> = {
    dashboard: ["Portfolio Overview", ""],
    assess: ["New Assessment", ""],
    cases: ["Case History", "All assessed applications"],
    case: ["Case Detail", "Full decision and cited findings"],
  };
  const [title, sub] = titles[view.name];
  const initials = user.slice(0, 2).toUpperCase();

  return (
    <div className="app">
      <aside className={"sidebar" + (collapsed ? " collapsed" : "")}>
        <div className="side-head">
          {/* Collapsed → the logo doubles as the expand button (fades to reveal a ›). */}
          <button
            className="brand-btn"
            onClick={collapsed ? toggleSidebar : undefined}
            aria-label={collapsed ? "Expand sidebar" : "Underwriting Engine"}
          >
            <span className="logo">UW</span>
            {collapsed && <span className="brand-expand"><ChevronRight /></span>}
            <span className="brand-meta">
              <span className="name">Underwriting</span>
              <span className="tag">Engine · L&amp;H</span>
            </span>
          </button>
          <button className="collapse-btn" onClick={toggleSidebar} aria-label="Collapse sidebar">
            <ChevronLeft />
          </button>
        </div>

        <nav className="side-nav" aria-label="Primary">
          <NavItem icon={<IconDashboard />} label="Dashboard" active={view.name === "dashboard"} onClick={() => nav("dashboard")} />
          <NavItem icon={<IconAssess />} label="New Assessment" active={view.name === "assess"} onClick={() => nav("assess")} />
          <NavItem icon={<IconCases />} label="Case History" active={view.name === "cases" || view.name === "case"} onClick={() => nav("cases")} />
        </nav>

        <div className="spacer" />

        <div className="side-foot">
          <button className="nav-item theme-toggle" onClick={toggleDark} aria-label={dark ? "Light mode" : "Dark mode"}>
            <span className="ic"><ThemeIcon dark={dark} /></span>
            <span className="nav-label">{dark ? "Light mode" : "Dark mode"}</span>
            <span className="nav-tip">{dark ? "Light mode" : "Dark mode"}</span>
          </button>
          <UserMenu user={user} initials={initials} onLogout={logout} />
        </div>
      </aside>

      <main className="main glass-nav">
        <div className="topbar">
          <div>
            <h1>{title}</h1>
            {sub && <div className="sub">{sub}</div>}
          </div>
        </div>
        <div className="content">
          {view.name === "dashboard" && <Dashboard key={tick} go={openCase} />}
          {view.name === "assess" && <Wizard go={openCase} onSaved={() => setTick((t) => t + 1)} />}
          {view.name === "cases" && <Cases key={tick} go={openCase} />}
          {view.name === "case" && <CaseDetail id={view.id} back={() => nav("cases")} />}
        </div>
      </main>
    </div>
  );
}

function NavItem({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return (
    <button className={"nav-item" + (active ? " active" : "")} onClick={onClick} aria-label={label}>
      <span className="ic">{icon}</span>
      <span className="nav-label">{label}</span>
      <span className="nav-tip">{label}</span>
    </button>
  );
}

/* Avatar + popover menu pinned to the sidebar foot — mirrors etimad's UserMenuTrigger. */
function UserMenu({ user, initials, onLogout }: { user: string; initials: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, [open]);

  return (
    <div className="user-wrap" ref={wrapRef}>
      <button className="user-btn" onClick={() => setOpen((v) => !v)} aria-haspopup="menu" aria-expanded={open}>
        <span className="user-avatar">{initials}</span>
        <span className="user-meta">
          <span className="u-name">{user}</span>
          <span className="u-role">Underwriter</span>
        </span>
        <span className="nav-tip">{user}</span>
      </button>
      {open && (
        <div className="user-menu" role="menu">
          <div className="um-head">
            <div className="um-name">{user}</div>
            <div className="um-sub">Signed in · Underwriter</div>
          </div>
          <button className="um-item danger" onClick={onLogout} role="menuitem">
            <IconLogout /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

/* ---- Inline icons (uniform 20×20, stroke 2.1) so the rail aligns cleanly ---- */
function IconDashboard() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  );
}
function IconAssess() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" />
      <line x1="12" y1="11" x2="12" y2="17" /><line x1="9" y1="14" x2="15" y2="14" />
    </svg>
  );
}
function IconCases() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}
function IconLogout() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}
function ChevronLeft() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}
function ChevronRight() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

// Animated sun↔moon morph (rays fade/shrink; a mask carves the crescent), ported
// from etimad's ThemeToggle but driven by CSS transitions instead of framer-motion.
function ThemeIcon({ dark }: { dark: boolean }) {
  return (
    <svg
      width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.2" strokeLinecap="round"
      style={{ transform: `rotate(${dark ? 270 : 0}deg)`, transition: "transform 400ms cubic-bezier(0.4,0,0.2,1)", overflow: "visible" }}
    >
      <mask id="theme-moon-mask">
        <rect x="0" y="0" width="100%" height="100%" fill="white" />
        <circle cx={dark ? 17 : 33} cy={dark ? 8 : 0} r="9" fill="black" style={{ transition: "cx 400ms cubic-bezier(0.4,0,0.2,1), cy 400ms cubic-bezier(0.4,0,0.2,1)" }} />
      </mask>
      <circle cx="12" cy="12" r={dark ? 9 : 5} fill="currentColor" stroke="none" mask="url(#theme-moon-mask)" style={{ transition: "r 400ms cubic-bezier(0.4,0,0.2,1)" }} />
      <g style={{ opacity: dark ? 0 : 1, transform: dark ? "scale(0) rotate(-30deg)" : "scale(1)", transformOrigin: "12px 12px", transition: "opacity 400ms, transform 400ms cubic-bezier(0.4,0,0.2,1)" }}>
        <line x1="12" y1="1" x2="12" y2="3" />
        <line x1="12" y1="21" x2="12" y2="23" />
        <line x1="1" y1="12" x2="3" y2="12" />
        <line x1="21" y1="12" x2="23" y2="12" />
        <line x1="5.64" y1="5.64" x2="4.22" y2="4.22" />
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        <line x1="5.64" y1="18.36" x2="4.22" y2="19.78" />
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      </g>
    </svg>
  );
}
