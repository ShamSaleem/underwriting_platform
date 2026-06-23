import { useEffect, useState } from "react";
import { api, CaseSummary, Decision, DecisionCode, Stats, UploadResult } from "./api";

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

/* ---------------------------------------------------------------- Assess */
const SAMPLES: Record<string, any> = {
  Clean: {
    applicant_type: "individual", product: "individual_life", sum_assured: 300000,
    annual_income: 80000, existing_life_cover: 0,
    full_name: "Aisha Bello", age: 34, sex: "female", smoking: "non_smoker",
    occupation: "software engineer", occupation_class: 1,
    height_cm: 165, weight_kg: 60, hba1c: "", systolic_bp: "", diastolic_bp: "",
    avocations: "", foreign_travel: "", family_history: "", disclosures: "",
  },
  Diabetic: {
    applicant_type: "individual", product: "individual_life", sum_assured: 750000,
    annual_income: 90000, existing_life_cover: 200000,
    full_name: "John Carter", age: 47, sex: "male", smoking: "occasional",
    occupation: "warehouse supervisor", occupation_class: 4,
    height_cm: 178, weight_kg: 104, hba1c: 7.4, systolic_bp: 148, diastolic_bp: 92,
    avocations: "recreational scuba diving to 30m, ~10 dives/year",
    foreign_travel: "quarterly trips to Nigeria",
    family_history: "father had a heart attack at 55",
    disclosures: "Type 2 diabetes | diagnosed 4 years ago, on metformin, no complications",
  },
};

function Assess({ onSaved }: { onSaved: () => void }) {
  const [f, setF] = useState<any>(SAMPLES.Diabetic);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Decision | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: string, v: any) => setF((p: any) => ({ ...p, [k]: v }));
  const isGroup = f.applicant_type === "group";

  function buildBody() {
    const num = (v: any) => (v === "" || v == null ? undefined : Number(v));
    const base: any = {
      applicant_type: f.applicant_type,
      product: f.product,
      sum_assured: Number(f.sum_assured),
      financials: { annual_income: Number(f.annual_income || 0), existing_life_cover: Number(f.existing_life_cover || 0) },
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
        occupation: f.occupation || "",
        occupation_class: num(f.occupation_class),
        avocations: lines(String(f.avocations || "")),
        foreign_travel: lines(String(f.foreign_travel || "")),
        family_history: lines(String(f.family_history || "")),
        medical_disclosures: lines(String(f.disclosures || "")).map((l) => {
          const [c, d] = l.split("|");
          return { condition: (c || "").trim(), details: (d || "").trim() || null };
        }),
        metrics: {
          height_cm: num(f.height_cm), weight_kg: num(f.weight_kg),
          hba1c: num(f.hba1c), systolic_bp: num(f.systolic_bp), diastolic_bp: num(f.diastolic_bp),
        },
      };
    }
    return base;
  }

  async function submit() {
    setBusy(true); setErr(null); setResult(null);
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

  return (
    <div className="row-2">
      <div className="card">
        <div className="toolbar" style={{ marginBottom: 18 }}>
          <div className="seg">
            <button className={!isGroup ? "on" : ""} onClick={() => set("applicant_type", "individual")}>Individual</button>
            <button className={isGroup ? "on" : ""} onClick={() => set("applicant_type", "group")}>Group / Company</button>
          </div>
          <div className="spacer" style={{ flex: 1 }} />
          {!isGroup && (
            <>
              <button className="btn ghost" onClick={() => setF(SAMPLES.Clean)}>Sample: clean</button>
              <button className="btn ghost" onClick={() => setF(SAMPLES.Diabetic)}>Sample: complex</button>
            </>
          )}
        </div>

        <div className="form-grid">
          <Field label="Product">
            <select value={f.product} onChange={(e) => set("product", e.target.value)}>
              {["individual_life","group_life","critical_illness","disability_income","medical","credit_life"].map((p) => (
                <option key={p} value={p}>{p.replace(/_/g, " ")}</option>
              ))}
            </select>
          </Field>
          <Field label="Sum assured (USD)">
            <input type="number" value={f.sum_assured} onChange={(e) => set("sum_assured", e.target.value)} />
          </Field>
          <Field label="Annual income (USD)">
            <input type="number" value={f.annual_income} onChange={(e) => set("annual_income", e.target.value)} />
          </Field>
          <Field label="Existing life cover (USD)">
            <input type="number" value={f.existing_life_cover} onChange={(e) => set("existing_life_cover", e.target.value)} />
          </Field>

          {!isGroup ? (
            <>
              <Field label="Full name"><input value={f.full_name} onChange={(e) => set("full_name", e.target.value)} /></Field>
              <Field label="Age"><input type="number" value={f.age} onChange={(e) => set("age", e.target.value)} /></Field>
              <Field label="Sex">
                <select value={f.sex} onChange={(e) => set("sex", e.target.value)}>
                  <option value="male">male</option><option value="female">female</option><option value="other">other</option>
                </select>
              </Field>
              <Field label="Smoking">
                <select value={f.smoking} onChange={(e) => set("smoking", e.target.value)}>
                  <option value="non_smoker">non-smoker</option><option value="occasional">occasional</option><option value="regular">regular</option>
                </select>
              </Field>
              <Field label="Occupation"><input value={f.occupation} onChange={(e) => set("occupation", e.target.value)} /></Field>
              <Field label="Occupation class (1–6)"><input type="number" value={f.occupation_class} onChange={(e) => set("occupation_class", e.target.value)} /></Field>
              <Field label="Height (cm)"><input type="number" value={f.height_cm} onChange={(e) => set("height_cm", e.target.value)} /></Field>
              <Field label="Weight (kg)"><input type="number" value={f.weight_kg} onChange={(e) => set("weight_kg", e.target.value)} /></Field>
              <Field label="HbA1c (%)"><input type="number" value={f.hba1c} onChange={(e) => set("hba1c", e.target.value)} /></Field>
              <Field label="Blood pressure (sys / dia)">
                <div style={{ display: "flex", gap: 8 }}>
                  <input type="number" placeholder="sys" value={f.systolic_bp} onChange={(e) => set("systolic_bp", e.target.value)} />
                  <input type="number" placeholder="dia" value={f.diastolic_bp} onChange={(e) => set("diastolic_bp", e.target.value)} />
                </div>
              </Field>
              <Field label="Avocations (one per line)" full><textarea value={f.avocations} onChange={(e) => set("avocations", e.target.value)} /></Field>
              <Field label="Foreign travel / residency (one per line)" full><textarea value={f.foreign_travel} onChange={(e) => set("foreign_travel", e.target.value)} /></Field>
              <Field label="Family history (one per line)" full><textarea value={f.family_history} onChange={(e) => set("family_history", e.target.value)} /></Field>
              <Field label="Medical disclosures — one per line as: condition | details" full>
                <textarea value={f.disclosures} onChange={(e) => set("disclosures", e.target.value)} />
              </Field>
            </>
          ) : (
            <>
              <Field label="Company name"><input value={f.company_name || ""} onChange={(e) => set("company_name", e.target.value)} /></Field>
              <Field label="Industry"><input value={f.industry || ""} onChange={(e) => set("industry", e.target.value)} /></Field>
              <Field label="Number of employees"><input type="number" value={f.num_employees || ""} onChange={(e) => set("num_employees", e.target.value)} /></Field>
              <Field label="Average age"><input type="number" value={f.average_age || ""} onChange={(e) => set("average_age", e.target.value)} /></Field>
              <Field label="Occupation classes (comma separated)"><input value={f.occupation_classes || ""} onChange={(e) => set("occupation_classes", e.target.value)} /></Field>
              <Field label="Free cover limit requested (USD)"><input type="number" value={f.free_cover_limit_requested || ""} onChange={(e) => set("free_cover_limit_requested", e.target.value)} /></Field>
              <Field label="Notes" full><textarea value={f.notes || ""} onChange={(e) => set("notes", e.target.value)} /></Field>
            </>
          )}
        </div>

        <div className="toolbar" style={{ marginTop: 20 }}>
          <button className="btn primary" onClick={submit} disabled={busy}>
            {busy ? <span className="spinner" /> : "Assess eligibility →"}
          </button>
          {err && <span style={{ color: "var(--red)", fontSize: 13 }}>{err}</span>}
        </div>
      </div>

      <div className="card">
        <div className="section-title" style={{ marginTop: 0 }}>Decision</div>
        {result ? <DecisionView d={result} /> : (
          <div className="empty">Fill the form and run an assessment.<br />The decision and cited findings appear here.</div>
        )}
      </div>
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
type View = { name: "dashboard" | "assess" | "batch" | "cases" } | { name: "case"; id: string };

export default function App() {
  const [user, setUser] = useState<string | null>(() => localStorage.getItem("aegis_user"));
  const [view, setView] = useState<View>({ name: "dashboard" });
  const [tick, setTick] = useState(0); // refresh dashboard after a save

  const nav = (n: "dashboard" | "assess" | "batch" | "cases") => setView({ name: n });
  const openCase = (id: string) => setView({ name: "case", id });
  const logout = () => { localStorage.removeItem("aegis_user"); setUser(null); };

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
    batch: ["Bulk Assessment", "Upload an Excel of applicants — single or many"],
    cases: ["Case History", "All assessed applications"],
    case: ["Case Detail", "Full decision and cited findings"],
  };
  const [title, sub] = titles[view.name];
  const initials = user.slice(0, 2).toUpperCase();

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo">UW</div>
          <div>
            <div className="name">Underwriting</div>
            <div className="tag">Engine · L&amp;H</div>
          </div>
        </div>
        <NavItem ic="▦" label="Dashboard" active={view.name === "dashboard"} onClick={() => nav("dashboard")} />
        <NavItem ic="✚" label="New Assessment" active={view.name === "assess"} onClick={() => nav("assess")} />
        <NavItem ic="⤒" label="Bulk Assessment" active={view.name === "batch"} onClick={() => nav("batch")} />
        <NavItem ic="≣" label="Case History" active={view.name === "cases" || view.name === "case"} onClick={() => nav("cases")} />
        <div className="spacer" />
      </aside>

      <main className="main">
        <div className="topbar">
          <div>
            <h1>{title}</h1>
            {sub && <div className="sub">{sub}</div>}
          </div>
          <div className="right">
            <button className="btn ghost" onClick={logout}>Logout</button>
            <div className="avatar">{initials}</div>
          </div>
        </div>
        <div className="content">
          {view.name === "dashboard" && <Dashboard key={tick} go={openCase} />}
          {view.name === "assess" && <Assess onSaved={() => setTick((t) => t + 1)} />}
          {view.name === "batch" && <Batch go={openCase} onDone={() => setTick((t) => t + 1)} />}
          {view.name === "cases" && <Cases key={tick} go={openCase} />}
          {view.name === "case" && <CaseDetail id={view.id} back={() => nav("cases")} />}
        </div>
      </main>
    </div>
  );
}

function NavItem({ ic, label, active, onClick }: { ic: string; label: string; active: boolean; onClick: () => void }) {
  return (
    <button className={"nav-item" + (active ? " active" : "")} onClick={onClick}>
      <span className="ic">{ic}</span> {label}
    </button>
  );
}
