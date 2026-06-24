"use client";

import { useEffect, useState } from "react";
import { api, formatApiError, OUTCOME_BADGE_STYLES, type Approval, type Lead } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

const EMPTY_FORM = {
  title: "",
  description: "",
  budget: "",
  skills: "",
  fit: "",
  profitability: "",
  client_quality: "",
};

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [online, setOnline] = useState(true);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [resolving, setResolving] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const [l, a] = await Promise.all([api.leads(), api.approvals()]);
        if (!active) return;
        setLeads(l);
        setApprovals(a);
        setOnline(true);
      } catch {
        if (active) setOnline(false);
      }
    }
    poll();
    const id = setInterval(poll, 2500);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  async function submitFiverrLead() {
    const title = form.title.trim();
    const description = form.description.trim();
    if (!title && !description) {
      setFormError("Paste in a title or description from the Fiverr listing.");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const factors: Record<string, number> = {};
      if (form.fit) factors.fit = Number(form.fit);
      if (form.profitability) factors.profitability = Number(form.profitability);
      if (form.client_quality) factors.client_quality = Number(form.client_quality);

      const lead = await api.submitFiverrLead({
        title,
        description,
        budget: form.budget ? Number(form.budget) : undefined,
        skills: form.skills
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        factors: Object.keys(factors).length ? factors : undefined,
      });
      setLeads((prev) => [lead, ...prev]);
      setForm(EMPTY_FORM);
    } catch (err) {
      setFormError(formatApiError(err, "Could not submit the lead."));
    } finally {
      setSubmitting(false);
    }
  }

  async function resolveApproval(id: string, approve: boolean) {
    setResolving(id);
    try {
      await api.recordOutcome(id, {
        actual_outcome: approve ? "operator_approved" : "operator_rejected",
        outcome_quality: approve ? 1 : -1,
      });
      setApprovals((prev) => prev.filter((a) => a.id !== id));
    } catch (err) {
      setFormError(formatApiError(err, "Could not record the operator decision."));
    } finally {
      setResolving(null);
    }
  }

  return (
    <div className="h-full overflow-y-auto p-8">
      <PageHeader
        title="Leads & Approvals"
        subtitle="Score freelance leads and clear what's waiting on you."
        online={online}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 font-display text-sm uppercase tracking-widest text-text-secondary">
            Paste a Fiverr listing
          </h2>
          <p className="mb-3 font-mono text-[10px] text-text-secondary">
            Fiverr has no API. This is manual paste-in only — nothing is ever scraped.
          </p>
          <div className="glass space-y-3 rounded-xl p-5">
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="Listing title"
              className="w-full rounded-lg border border-border bg-bg/40 px-3 py-2 font-body text-sm text-text-primary outline-none focus:border-primary"
            />
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Listing description"
              rows={3}
              className="w-full resize-none rounded-lg border border-border bg-bg/40 px-3 py-2 font-body text-sm text-text-primary outline-none focus:border-primary"
            />
            <div className="grid grid-cols-2 gap-3">
              <input
                value={form.budget}
                onChange={(e) => setForm({ ...form, budget: e.target.value })}
                placeholder="Budget (USD)"
                type="number"
                className="rounded-lg border border-border bg-bg/40 px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-primary"
              />
              <input
                value={form.skills}
                onChange={(e) => setForm({ ...form, skills: e.target.value })}
                placeholder="Skills (comma separated)"
                className="rounded-lg border border-border bg-bg/40 px-3 py-2 font-body text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <input
                value={form.fit}
                onChange={(e) => setForm({ ...form, fit: e.target.value })}
                placeholder="Fit (0-10)"
                type="number"
                className="rounded-lg border border-border bg-bg/40 px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-primary"
              />
              <input
                value={form.profitability}
                onChange={(e) => setForm({ ...form, profitability: e.target.value })}
                placeholder="Profit (0-10)"
                type="number"
                className="rounded-lg border border-border bg-bg/40 px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-primary"
              />
              <input
                value={form.client_quality}
                onChange={(e) => setForm({ ...form, client_quality: e.target.value })}
                placeholder="Client (0-10)"
                type="number"
                className="rounded-lg border border-border bg-bg/40 px-3 py-2 font-mono text-sm text-text-primary outline-none focus:border-primary"
              />
            </div>
            <button
              onClick={submitFiverrLead}
              disabled={submitting}
              className="btn-scan w-full rounded-full bg-primary px-6 py-2 font-display text-sm font-medium text-white transition-all hover:bg-active disabled:cursor-not-allowed disabled:opacity-40"
            >
              {submitting ? "Scoring…" : "Score lead"}
            </button>
            {formError && <p className="font-mono text-xs text-error">{formError}</p>}
          </div>

          <h2 className="mb-3 mt-8 font-display text-sm uppercase tracking-widest text-text-secondary">
            Scored leads
          </h2>
          <div className="space-y-2">
            {leads.map((lead) => (
              <div key={lead.id} className="glass rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <span className="font-body text-sm text-text-primary">{lead.title}</span>
                  {lead.score !== undefined && (
                    <span className="font-mono text-xs text-active">{lead.score}/10</span>
                  )}
                </div>
                <p className="mt-1 line-clamp-2 font-body text-xs text-text-secondary">
                  {lead.description}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-[10px] text-text-secondary">
                  <span className="rounded-full border border-border px-2 py-0.5">
                    {lead.source}
                  </span>
                  {lead.budget_amount != null && (
                    <span>
                      {lead.budget_currency} {lead.budget_amount}
                    </span>
                  )}
                </div>
              </div>
            ))}
            {leads.length === 0 && (
              <div className="font-mono text-sm text-text-secondary">
                No leads scored yet.
              </div>
            )}
          </div>
        </section>

        <section>
          <h2 className="mb-3 font-display text-sm uppercase tracking-widest text-text-secondary">
            Waiting on you
          </h2>
          <div className="space-y-2">
            {approvals.map((a) => (
              <div key={a.id} className="glass rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-active">{a.brain_id}</span>
                  <span
                    className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase ${OUTCOME_BADGE_STYLES.REQUEST_MORE_EVIDENCE}`}
                  >
                    needs operator
                  </span>
                </div>
                <p className="mt-2 font-body text-sm text-text-primary">{a.belief}</p>
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => resolveApproval(a.id, true)}
                    disabled={resolving === a.id}
                    className="rounded-full border border-success/40 bg-success/10 px-4 py-1 font-mono text-xs text-success transition-colors hover:bg-success/20 disabled:opacity-40"
                  >
                    Confirm
                  </button>
                  <button
                    onClick={() => resolveApproval(a.id, false)}
                    disabled={resolving === a.id}
                    className="rounded-full border border-error/40 bg-error/10 px-4 py-1 font-mono text-xs text-error transition-colors hover:bg-error/20 disabled:opacity-40"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
            {approvals.length === 0 && (
              <div className="font-mono text-sm text-text-secondary">
                Nothing waiting on you right now.
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
