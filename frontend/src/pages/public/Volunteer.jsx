import React from "react";
import { useNavigate } from "react-router-dom";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { IMG } from "@/lib/images";
import { Clock, MapPin, Laptop, HeartHandshake, ArrowRight } from "lucide-react";

export default function Volunteer() {
  const navigate = useNavigate();
  const opps = [
    { i: HeartHandshake, t: "Event Support", d: "Help plan and run CEC community events and outreach days." },
    { i: Laptop, t: "Virtual Assistance", d: "Support marketing, social media, and administrative tasks remotely." },
    { i: MapPin, t: "Local Outreach", d: "Represent the CEC at in-person meetups and partner activities." },
    { i: Clock, t: "Flexible Hours", d: "Contribute on a schedule that works for you — every hour counts." },
  ];
  return (
    <PublicLayout>
      <section className="relative bg-brand-navy-dark text-white py-20 overflow-hidden">
        <img src={IMG.hands} alt="" className="absolute inset-0 w-full h-full object-cover opacity-25" />
        <div className="absolute inset-0 bg-gradient-to-r from-brand-navy-dark to-brand-navy-dark/50" />
        <div className="relative max-w-7xl mx-auto px-4">
          <SectionHeading light eyebrow="Give Back" title="Volunteer Opportunities" subtitle="Lend your time and talent to the CEC. Volunteers power our events, programs, and community connections." />
          <Button onClick={() => navigate("/apply")} className="mt-8 rounded-full bg-brand-magenta hover:bg-brand-pink h-12 px-7">Become a Volunteer <ArrowRight size={18} className="ml-1" /></Button>
        </div>
      </section>
      <section className="max-w-7xl mx-auto px-4 py-16">
        <SectionHeading center eyebrow="How You Can Help" title="Ways to volunteer" />
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 mt-10">
          {opps.map((o, i) => (
            <div key={i} className="bg-white border border-slate-200 rounded-2xl p-6 hover:-translate-y-1 hover:shadow-lg transition-all">
              <div className="h-11 w-11 rounded-xl bg-brand-navy text-white flex items-center justify-center mb-4"><o.i size={20} /></div>
              <h3 className="font-head font-bold text-brand-navy">{o.t}</h3>
              <p className="text-slate-600 text-sm mt-2">{o.d}</p>
            </div>
          ))}
        </div>
      </section>
    </PublicLayout>
  );
}
