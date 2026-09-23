import React from "react";
import { Link } from "react-router-dom";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { IMG } from "@/lib/images";
import { GraduationCap, Briefcase, Users, Truck, Baby, Sparkles, HeartHandshake, Award, CalendarDays, Compass, ArrowRight, ExternalLink } from "lucide-react";

const DT_PROGRAMS = "https://dt-platform.emergent.host/programs";
const DT_INTAKE = "https://dt-platform.emergent.host/intake";

const PROGRAMS = [
  { i: GraduationCap, t: "Education & Career Pathways", d: "CDL awareness, mentorship, and pathways into trucking, logistics, transportation and supply chain careers." },
  { i: Briefcase, t: "Workforce Development", d: "Connecting women to careers, training and referrals across transportation and logistics.", img: IMG.training },
  { i: Truck, t: "Trucking & Transportation", d: "Industry advocacy, safety, and representation for women behind the wheel." },
  { i: Users, t: "Community Outreach", d: "Local events, partnerships, and membership growth in every state we serve." },
  { i: Award, t: "Ambassador Leadership", d: "State Ambassadors who represent AAWTA, lead locally, and grow the community." },
  { i: HeartHandshake, t: "Volunteer Service", d: "Volunteers who power our events, mentorship and community programs — and log service hours." },
  { i: CalendarDays, t: "Events & Industry Engagement", d: "Workshops, career fairs, networking and industry events across the country." },
  { i: Baby, t: "Youth & Workforce Opportunities", d: "Inspiring the next generation to explore and enter careers in the industry." },
  { i: Sparkles, t: "Entrepreneurship", d: "Supporting women building their own trucking and logistics businesses." },
];

const CTAS = [
  { label: "Become an Ambassador", to: "/apply?type=ambassador" },
  { label: "Volunteer", to: "/apply?type=volunteer" },
  { label: "Explore Education Programs", href: DT_PROGRAMS },
  { label: "Take the SMART Assessment", href: DT_INTAKE },
  { label: "View Events", to: "/events" },
];

export default function Programs() {
  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-16">
        <div className="max-w-7xl mx-auto px-4">
          <SectionHeading light eyebrow="Impact" title="Programs & Community Impact" subtitle="From classrooms to loading docks, the CEC connects community engagement, workforce development, education, trucking & logistics, volunteerism and career pathways across AAWTA." />
        </div>
      </section>

      {/* Driven Together — prominent bridge section */}
      <section className="max-w-7xl mx-auto px-4 -mt-10">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-magenta to-brand-navy text-white shadow-xl" data-testid="driven-together-section">
          <div className="absolute inset-0 opacity-10" style={{ backgroundImage: "radial-gradient(circle at 20% 20%, white 1px, transparent 1px)", backgroundSize: "22px 22px" }} />
          <div className="relative p-8 sm:p-12">
            <div className="inline-flex items-center gap-2 bg-white/15 backdrop-blur px-3 py-1 rounded-full text-xs font-semibold tracking-wide"><Compass size={14} /> DRIVEN TOGETHER EDUCATION PROGRAM</div>
            <h2 className="font-head text-3xl sm:text-4xl font-extrabold mt-4 max-w-2xl">Turn interest into opportunity.</h2>
            <p className="text-white/85 mt-3 max-w-2xl leading-relaxed">
              Explore AAWTA's education and career-development pathways designed to help individuals enter and advance within trucking, logistics, transportation, and supply chain careers.
            </p>
            <div className="flex flex-wrap gap-3 mt-6">
              <a href={DT_PROGRAMS} target="_blank" rel="noreferrer" data-testid="dt-explore-btn">
                <Button className="rounded-full bg-white text-brand-navy hover:bg-white/90 h-12 px-6 font-semibold">Explore Education Programs <ArrowRight size={16} className="ml-1" /></Button>
              </a>
              <a href={DT_INTAKE} target="_blank" rel="noreferrer" data-testid="dt-smart-btn">
                <Button variant="outline" className="rounded-full h-12 px-6 font-semibold bg-transparent border-white/60 text-white hover:bg-white/10">Take the FREE SMART Assessment <ExternalLink size={15} className="ml-1" /></Button>
              </a>
            </div>
            <div className="mt-5 bg-white/10 backdrop-blur rounded-xl p-4 max-w-2xl">
              <p className="text-sm text-white/90"><span className="font-semibold">Not sure where to start?</span> Take our FREE SMART Assessment to help identify the education and career pathway that best aligns with your goals.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Ecosystem grid */}
      <section className="max-w-7xl mx-auto px-4 py-16">
        <h2 className="font-head text-2xl font-bold text-brand-navy mb-2">The CEC & AAWTA ecosystem</h2>
        <p className="text-slate-600 mb-8 max-w-2xl">Every program works together — from first spark of interest to active leadership and career growth.</p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {PROGRAMS.map((p, i) => (
            <div key={i} className="bg-white border border-slate-200 rounded-2xl overflow-hidden hover:shadow-lg transition-shadow" data-testid={`program-card-${i}`}>
              {p.img && <img src={p.img} alt={p.t} className="h-40 w-full object-cover" />}
              <div className="p-6">
                <div className="h-11 w-11 rounded-xl bg-brand-magenta/10 text-brand-magenta flex items-center justify-center mb-4"><p.i size={20} /></div>
                <h3 className="font-head font-bold text-brand-navy">{p.t}</h3>
                <p className="text-slate-600 text-sm mt-2 leading-relaxed">{p.d}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA band */}
      <section className="bg-slate-50 border-t border-slate-200 py-14">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <h2 className="font-head text-2xl font-bold text-brand-navy">Take your next step</h2>
          <p className="text-slate-600 mt-2 mb-7 max-w-xl mx-auto">Whether you want to lead, serve, learn or attend — there's a place for you.</p>
          <div className="flex flex-wrap justify-center gap-3">
            {CTAS.map((c) => c.href ? (
              <a key={c.label} href={c.href} target="_blank" rel="noreferrer" data-testid={`cta-${c.label.replace(/\s+/g, "-").toLowerCase()}`}>
                <Button variant="outline" className="rounded-full h-11 px-5 border-brand-navy/25 text-brand-navy hover:bg-brand-navy hover:text-white">{c.label} <ExternalLink size={14} className="ml-1" /></Button>
              </a>
            ) : (
              <Link key={c.label} to={c.to} data-testid={`cta-${c.label.replace(/\s+/g, "-").toLowerCase()}`}>
                <Button className="rounded-full h-11 px-5 bg-brand-magenta hover:bg-brand-pink">{c.label} <ArrowRight size={14} className="ml-1" /></Button>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
