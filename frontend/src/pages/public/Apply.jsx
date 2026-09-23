import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, CheckCircle2, Award, HeartHandshake } from "lucide-react";
import { PublicLayout } from "@/components/PublicLayout";
import { Button } from "@/components/ui/button";
import { Field, SelectField, MultiChips, Consent, FileField } from "@/components/FormFields";
import { US_STATES, FOCUS_AREAS } from "@/lib/constants";
import { api } from "@/auth";

const Section = ({ title, children }) => (
  <div className="space-y-4">
    <h3 className="font-head font-bold text-brand-navy border-b border-slate-100 pb-2">{title}</h3>
    {children}
  </div>
);

export default function Apply() {
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get("type") === "volunteer" ? "volunteer" : "ambassador");
  const [f, setF] = useState({ areas_of_interest: [] });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (f.company_website) return;
    if (!f.certify || !f.consent) { toast.error("Please provide the required consents."); return; }
    setBusy(true);
    try {
      const payload = { ...f };
      const { data } = await api.post("/public/applications", { type: tab, data: payload, honeypot: f.company_website || "" });
      setDone(data.ref);
      toast.success("Application submitted!");
    } catch (err) { toast.error(err?.response?.data?.detail || "Submission failed"); }
    setBusy(false);
  };

  if (done) return (
    <PublicLayout><div className="max-w-lg mx-auto px-4 py-24 text-center">
      <CheckCircle2 className="mx-auto text-emerald-500 mb-4" size={56} />
      <h1 className="font-head text-3xl font-extrabold text-brand-navy">Application received!</h1>
      <p className="text-slate-600 mt-3">Thank you for applying. Your reference number is <span className="font-mono-data font-bold text-brand-magenta">{done}</span>. Watch your inbox for a confirmation email. Portal access is granted only after approval.</p>
    </div></PublicLayout>
  );

  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-14"><div className="max-w-7xl mx-auto px-4 text-center">
        <h1 className="font-head text-4xl font-extrabold">Apply to the CEC</h1>
        <p className="text-white/70 mt-2">Choose how you'd like to get involved.</p>
        <div className="inline-flex mt-6 bg-white/10 rounded-full p-1">
          <button data-testid="tab-ambassador" onClick={() => setTab("ambassador")} className={`px-5 py-2 rounded-full text-sm font-semibold flex items-center gap-2 transition-colors ${tab === "ambassador" ? "bg-brand-magenta text-white" : "text-white/70"}`}><Award size={16} /> State Ambassador</button>
          <button data-testid="tab-volunteer" onClick={() => setTab("volunteer")} className={`px-5 py-2 rounded-full text-sm font-semibold flex items-center gap-2 transition-colors ${tab === "volunteer" ? "bg-brand-magenta text-white" : "text-white/70"}`}><HeartHandshake size={16} /> Volunteer</button>
        </div>
      </div></section>

      <section className="max-w-3xl mx-auto px-4 py-14">
        <form onSubmit={submit} className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-8 space-y-8" data-testid="application-form">
          <input type="text" name="company_website" value={f.company_website || ""} onChange={(e) => on("company_website", e.target.value)} className="hidden" tabIndex={-1} autoComplete="off" />

          <Section title="Contact Information">
            <div className="grid sm:grid-cols-2 gap-4">
              {tab === "ambassador" ? (<>
                <Field label="First name" name="first_name" value={f.first_name} onChange={on} required />
                <Field label="Last name" name="last_name" value={f.last_name} onChange={on} required />
              </>) : (
                <Field label="Full name" name="full_name" value={f.full_name} onChange={on} required />
              )}
              <Field label="Email" name="email" type="email" value={f.email} onChange={on} required />
              <Field label="Telephone" name="telephone" value={f.telephone} onChange={on} required />
              <Field label="City" name="city" value={f.city} onChange={on} />
              <SelectField label="State" name="state" value={f.state} onChange={on} options={US_STATES} />
            </div>
          </Section>

          {tab === "ambassador" && (<>
            <Section title="Address & Organization">
              <div className="grid sm:grid-cols-2 gap-4">
                <Field label="Street address" name="street" value={f.street} onChange={on} />
                <Field label="ZIP code" name="zip" value={f.zip} onChange={on} />
                <Field label="County" name="county" value={f.county} onChange={on} />
                <Field label="Company / organization" name="company" value={f.company} onChange={on} />
                <Field label="Job title" name="job_title" value={f.job_title} onChange={on} />
                <SelectField label="AAWTA membership status" name="membership_status" value={f.membership_status} onChange={on} options={["Current member", "Former member", "Not a member", "Interested in joining"]} />
                <Field label="AAWTA membership type" name="membership_type" value={f.membership_type} onChange={on} />
                <SelectField label="State you want to represent" name="represent_state" value={f.represent_state} onChange={on} options={US_STATES} required />
              </div>
            </Section>
            <Section title="Social Media">
              <div className="grid sm:grid-cols-2 gap-4">
                <Field label="LinkedIn" name="linkedin" value={f.linkedin} onChange={on} />
                <Field label="Facebook" name="facebook" value={f.facebook} onChange={on} />
                <Field label="Instagram" name="instagram" value={f.instagram} onChange={on} />
                <Field label="Other social media" name="other_social" value={f.other_social} onChange={on} />
              </div>
            </Section>
            <Section title="Ambassador Areas of Interest">
              <MultiChips label="Select one or more focus areas" options={FOCUS_AREAS} value={f.areas_of_interest} onChange={(v) => on("areas_of_interest", v)} />
            </Section>
            <Section title="Your Background">
              <Field label="Reason for applying" name="reason" value={f.reason} onChange={on} textarea required />
              <Field label="Relevant experience" name="experience" value={f.experience} onChange={on} textarea />
              <Field label="Community involvement" name="community" value={f.community} onChange={on} textarea />
              <Field label="Organizations / networks you're connected with" name="networks" value={f.networks} onChange={on} textarea />
            </Section>
            <Section title="Availability & Commitment">
              <div className="grid sm:grid-cols-2 gap-4">
                <Field label="Availability" name="availability" value={f.availability} onChange={on} />
                <Field label="Estimated monthly hours" name="monthly_hours" type="number" value={f.monthly_hours} onChange={on} />
              </div>
              <div className="space-y-2 pt-2">
                <Consent name="attend_meetings" checked={f.attend_meetings} onChange={on} label="I am willing to attend monthly meetings." />
                <Consent name="support_events" checked={f.support_events} onChange={on} label="I am willing to support AAWTA events." />
                <Consent name="submit_reports" checked={f.submit_reports} onChange={on} label="I am willing to submit monthly reports." />
              </div>
            </Section>
            <Section title="Documents">
              <div className="grid sm:grid-cols-3 gap-4">
                <FileField label="Resume" name="resume" value={f.resume} onChange={on} accept=".pdf,.doc,.docx" />
                <FileField label="Headshot" name="headshot" value={f.headshot} onChange={on} accept="image/*" />
                <FileField label="Supporting document" name="supporting" value={f.supporting} onChange={on} />
              </div>
            </Section>
          </>)}

          {tab === "volunteer" && (<>
            <Section title="About You">
              <Field label="Company / organization" name="company" value={f.company} onChange={on} />
              <Field label="Skills" name="skills" value={f.skills} onChange={on} textarea />
              <MultiChips label="Areas of interest" options={FOCUS_AREAS} value={f.areas_of_interest} onChange={(v) => on("areas_of_interest", v)} />
              <div className="grid sm:grid-cols-2 gap-4">
                <Field label="Event availability" name="availability" value={f.availability} onChange={on} />
                <SelectField label="Virtual or in-person" name="preference" value={f.preference} onChange={on} options={["Virtual", "In-person", "Both"]} />
                <Field label="Estimated hours available" name="monthly_hours" type="number" value={f.monthly_hours} onChange={on} />
              </div>
              <Field label="Relevant experience" name="experience" value={f.experience} onChange={on} textarea />
            </Section>
            <Section title="Documents (optional)">
              <div className="grid sm:grid-cols-3 gap-4">
                <FileField label="Resume" name="resume" value={f.resume} onChange={on} accept=".pdf,.doc,.docx" />
                <FileField label="Headshot" name="headshot" value={f.headshot} onChange={on} accept="image/*" />
                <FileField label="Supporting document" name="supporting" value={f.supporting} onChange={on} />
              </div>
            </Section>
          </>)}

          <Section title="How did you hear about us & consent">
            <Field label="How did you hear about this opportunity?" name="heard_about" value={f.heard_about} onChange={on} />
            <div className="space-y-2 pt-2">
              <Consent name="consent" checked={f.consent} onChange={on} label="I consent to receive email communications from AAWTA." />
              <Consent name="certify" checked={f.certify} onChange={on} label="I certify that the information provided is accurate, and I electronically acknowledge this submission." />
              <p className="text-xs text-slate-500 pt-1" data-testid="apply-legal-ack">By submitting, you acknowledge AAWTA's <a href="https://aawta.org/terms-and-conditions" target="_blank" rel="noreferrer" className="text-brand-magenta underline underline-offset-2">Terms &amp; Conditions</a> and <a href="https://aawta.org/privacy-policy" target="_blank" rel="noreferrer" className="text-brand-magenta underline underline-offset-2">Privacy Policy</a>.</p>
            </div>
          </Section>

          <Button type="submit" disabled={busy} data-testid="application-submit" className="w-full h-12 rounded-full bg-brand-magenta hover:bg-brand-pink text-base">
            {busy ? <Loader2 className="animate-spin" size={18} /> : `Submit ${tab === "ambassador" ? "Ambassador" : "Volunteer"} Application`}
          </Button>
        </form>
      </section>
    </PublicLayout>
  );
}
