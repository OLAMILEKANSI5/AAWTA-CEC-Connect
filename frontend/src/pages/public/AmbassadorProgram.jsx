import React from "react";
import { useNavigate } from "react-router-dom";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { IMG } from "@/lib/images";
import { FOCUS_AREAS } from "@/lib/constants";
import { CheckCircle2, ArrowRight } from "lucide-react";

export default function AmbassadorProgram() {
  const navigate = useNavigate();
  const responsibilities = ["Represent AAWTA in your assigned state", "Lead and support community events", "Create and track monthly goals", "Submit monthly activity reports", "Build strategic partnerships & referrals", "Attend monthly CEC meetings"];
  return (
    <PublicLayout>
      <section className="relative bg-brand-navy-dark text-white py-20 overflow-hidden">
        <img src={IMG.driver2} alt="" className="absolute inset-0 w-full h-full object-cover opacity-25" />
        <div className="absolute inset-0 bg-gradient-to-r from-brand-navy-dark to-brand-navy-dark/50" />
        <div className="relative max-w-7xl mx-auto px-4">
          <SectionHeading light eyebrow="Leadership Opportunity" title="State Ambassador Program" subtitle="Become the face of AAWTA in your state — lead initiatives, mentor others, and drive measurable community impact." />
          <Button onClick={() => navigate("/apply")} className="mt-8 rounded-full bg-brand-magenta hover:bg-brand-pink h-12 px-7">Apply to be an Ambassador <ArrowRight size={18} className="ml-1" /></Button>
        </div>
      </section>
      <section className="max-w-7xl mx-auto px-4 py-16 grid lg:grid-cols-2 gap-12">
        <div>
          <SectionHeading eyebrow="The Role" title="What Ambassadors do" />
          <ul className="mt-6 space-y-3">
            {responsibilities.map((r) => (<li key={r} className="flex items-start gap-3"><CheckCircle2 className="text-brand-magenta shrink-0 mt-0.5" size={20} /><span className="text-slate-700">{r}</span></li>))}
          </ul>
        </div>
        <div>
          <SectionHeading eyebrow="Areas of Focus" title="Choose your impact areas" />
          <div className="flex flex-wrap gap-2 mt-6">
            {FOCUS_AREAS.map((f) => (<span key={f} className="px-3 py-1.5 bg-brand-magenta/10 text-brand-magenta rounded-full text-sm font-medium">{f}</span>))}
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
