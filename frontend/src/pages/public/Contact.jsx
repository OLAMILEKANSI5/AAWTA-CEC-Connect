import React, { useState } from "react";
import { toast } from "sonner";
import { Loader2, CheckCircle2 } from "lucide-react";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Field, SelectField, Consent } from "@/components/FormFields";
import { INQUIRY_TYPES, US_STATES } from "@/lib/constants";
import { api } from "@/auth";

export default function Contact() {
  const [f, setF] = useState({});
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const on = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (f.company_website) return; // honeypot
    setBusy(true);
    try {
      const { data } = await api.post("/public/applications", { type: "inquiry", data: f, honeypot: f.company_website || "" });
      setDone(data.ref);
      toast.success("Inquiry submitted!");
    } catch (err) { toast.error(err?.response?.data?.detail || "Submission failed"); }
    setBusy(false);
  };

  if (done) return (
    <PublicLayout><div className="max-w-lg mx-auto px-4 py-24 text-center">
      <CheckCircle2 className="mx-auto text-emerald-500 mb-4" size={56} />
      <h1 className="font-head text-3xl font-extrabold text-brand-navy">Thank you!</h1>
      <p className="text-slate-600 mt-3">We received your inquiry. Your reference number is <span className="font-mono-data font-bold text-brand-magenta">{done}</span>. A confirmation email is on its way.</p>
    </div></PublicLayout>
  );

  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-16"><div className="max-w-7xl mx-auto px-4">
        <SectionHeading light eyebrow="Get in touch" title="Contact / Learn More" subtitle="Have a question, partnership idea, or want to learn more about the CEC? Send us a note." />
      </div></section>
      <section className="max-w-2xl mx-auto px-4 py-14">
        <form onSubmit={submit} className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-8 space-y-5" data-testid="inquiry-form">
          <input type="text" name="company_website" value={f.company_website || ""} onChange={(e) => on("company_website", e.target.value)} className="hidden" tabIndex={-1} autoComplete="off" />
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="Full name" name="full_name" value={f.full_name} onChange={on} required />
            <Field label="Email" name="email" type="email" value={f.email} onChange={on} required />
            <Field label="Telephone" name="telephone" value={f.telephone} onChange={on} />
            <Field label="Company / organization" name="company" value={f.company} onChange={on} />
            <Field label="City" name="city" value={f.city} onChange={on} />
            <SelectField label="State" name="state" value={f.state} onChange={on} options={US_STATES} />
          </div>
          <SelectField label="Type of inquiry" name="inquiry_type" value={f.inquiry_type} onChange={on} options={INQUIRY_TYPES} required />
          <Field label="Message" name="message" value={f.message} onChange={on} textarea required />
          <SelectField label="Preferred contact method" name="contact_method" value={f.contact_method} onChange={on} options={["Email", "Phone", "Either"]} />
          <Consent name="consent" checked={f.consent} onChange={on} label="I consent to receive communications from AAWTA regarding my inquiry." />
          <Button type="submit" disabled={busy} data-testid="inquiry-submit" className="w-full h-11 rounded-full bg-brand-magenta hover:bg-brand-pink">
            {busy ? <Loader2 className="animate-spin" size={18} /> : "Submit Inquiry"}
          </Button>
        </form>
      </section>
    </PublicLayout>
  );
}
