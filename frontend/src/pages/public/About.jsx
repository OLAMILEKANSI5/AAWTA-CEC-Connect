import React from "react";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading } from "@/components/shared";
import { IMG } from "@/lib/images";
import { Target, Eye, Compass } from "lucide-react";

export default function About() {
  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-16">
        <div className="max-w-7xl mx-auto px-4">
          <SectionHeading light eyebrow="About" title="The Community Engagement Committee" subtitle="Building bridges between the African American Women Trucking Association and the communities we serve." />
        </div>
      </section>
      <section className="max-w-7xl mx-auto px-4 py-16 grid lg:grid-cols-2 gap-12 items-center">
        <img src={IMG.logistics} alt="Women in logistics" className="rounded-2xl w-full h-96 object-cover" />
        <div>
          <SectionHeading eyebrow="Our Story" title="Empowerment through engagement" subtitle="The CEC mobilizes State Ambassadors and Volunteers across the country to advance opportunity, education, and representation for African American women in trucking, transportation, and logistics." />
          <p className="text-slate-600 mt-4 leading-relaxed">Through community outreach, mentorship, strategic partnerships, and workforce development, the CEC turns AAWTA's mission into local action — one state, one event, and one connection at a time.</p>
        </div>
      </section>
      <section className="bg-[#FAF5FB] py-16">
        <div className="max-w-7xl mx-auto px-4 grid md:grid-cols-3 gap-6">
          {[{ i: Target, t: "Mission", d: "Advance opportunity and representation for African American women in trucking through active community engagement." }, { i: Eye, t: "Vision", d: "A transportation industry where women lead, thrive, and uplift the communities around them." }, { i: Compass, t: "Values", d: "Empowerment, integrity, collaboration, service, and impact — in everything the CEC does." }].map((x, i) => (
            <div key={i} className="bg-white border border-slate-200 rounded-2xl p-7">
              <div className="h-12 w-12 rounded-xl bg-brand-magenta text-white flex items-center justify-center mb-4"><x.i size={22} /></div>
              <h3 className="font-head font-bold text-lg text-brand-navy">{x.t}</h3>
              <p className="text-slate-600 text-sm mt-2 leading-relaxed">{x.d}</p>
            </div>
          ))}
        </div>
      </section>
    </PublicLayout>
  );
}
