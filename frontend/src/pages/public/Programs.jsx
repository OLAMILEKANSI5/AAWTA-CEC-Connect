import React from "react";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading } from "@/components/shared";
import { IMG } from "@/lib/images";
import { GraduationCap, Briefcase, Users, Truck, Baby, Sparkles } from "lucide-react";

export default function Programs() {
  const programs = [
    { i: GraduationCap, t: "Education & Training", d: "CDL awareness, mentorship, and educational outreach for aspiring drivers.", img: IMG.training },
    { i: Briefcase, t: "Workforce Development", d: "Connecting women to careers and referrals across transportation and logistics." },
    { i: Truck, t: "Trucking & Transportation", d: "Industry advocacy, safety, and representation for women behind the wheel." },
    { i: Users, t: "Community Engagement", d: "Local events, partnerships, and membership growth in every state." },
    { i: Baby, t: "Youth Development", d: "Inspiring the next generation to explore careers in the industry." },
    { i: Sparkles, t: "Entrepreneurship", d: "Supporting women building their own trucking and logistics businesses." },
  ];
  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-16">
        <div className="max-w-7xl mx-auto px-4"><SectionHeading light eyebrow="Impact" title="Programs & Community Impact" subtitle="From classrooms to loading docks, the CEC delivers programs that create real, measurable opportunity." /></div>
      </section>
      <section className="max-w-7xl mx-auto px-4 py-16 grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {programs.map((p, i) => (
          <div key={i} className="bg-white border border-slate-200 rounded-2xl overflow-hidden hover:shadow-lg transition-shadow">
            {p.img && <img src={p.img} alt={p.t} className="h-40 w-full object-cover" />}
            <div className="p-6">
              <div className="h-11 w-11 rounded-xl bg-brand-magenta/10 text-brand-magenta flex items-center justify-center mb-4"><p.i size={20} /></div>
              <h3 className="font-head font-bold text-brand-navy">{p.t}</h3>
              <p className="text-slate-600 text-sm mt-2 leading-relaxed">{p.d}</p>
            </div>
          </div>
        ))}
      </section>
    </PublicLayout>
  );
}
