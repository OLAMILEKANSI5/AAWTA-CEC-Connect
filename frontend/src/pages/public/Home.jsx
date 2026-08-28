import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Truck, Users, MapPin, Calendar, Megaphone, GraduationCap, Briefcase, Heart, Handshake, Award } from "lucide-react";
import { PublicLayout } from "@/components/PublicLayout";
import { Button } from "@/components/ui/button";
import { SectionHeading } from "@/components/shared";
import { IMG } from "@/lib/images";
import { api, API } from "@/auth";

const fade = { hidden: { opacity: 0, y: 20 }, show: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.08, duration: 0.6, ease: [0.16, 1, 0.3, 1] } }) };

export default function Home() {
  const navigate = useNavigate();
  const [data, setData] = useState({ stats: {}, spotlights: [], announcements: [], events: [] });
  useEffect(() => { api.get("/public/home").then((r) => setData(r.data)).catch(() => {}); }, []);
  const s = data.stats || {};

  const ways = [
    { icon: Award, title: "Become a State Ambassador", desc: "Represent AAWTA in your state, lead initiatives, and champion women in trucking." },
    { icon: Handshake, title: "Volunteer Your Skills", desc: "Support events, mentorship, and community programs on your own schedule." },
    { icon: Heart, title: "Support the CEC", desc: "Partner, sponsor, or refer talent to help us expand our community impact." },
  ];
  const focus = [
    { icon: Truck, label: "Trucking & Transportation" }, { icon: GraduationCap, label: "Education" },
    { icon: Briefcase, label: "Workforce Development" }, { icon: Users, label: "Community Engagement" },
  ];

  return (
    <PublicLayout>
      {/* Hero */}
      <section className="relative overflow-hidden grain bg-brand-navy-dark">
        <img src={IMG.hero} alt="Woman truck driver" className="absolute inset-0 w-full h-full object-cover opacity-35" />
        <div className="absolute inset-0 bg-gradient-to-r from-brand-navy-dark via-brand-navy-dark/80 to-brand-navy-dark/30" />
        <div className="relative max-w-7xl mx-auto px-4 py-24 md:py-32">
          <motion.div initial="hidden" animate="show" className="max-w-2xl">
            <motion.div custom={0} variants={fade} className="inline-flex items-center gap-2 bg-brand-magenta/20 border border-brand-magenta/40 text-brand-pink text-xs font-semibold px-3 py-1.5 rounded-full mb-6">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-pink animate-pulse" /> AAWTA Community Engagement Committee
            </motion.div>
            <motion.h1 custom={1} variants={fade} className="font-head text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white leading-[1.05]">
              Connecting Ambassadors.<br /><span className="text-brand-pink">Engaging</span> Communities.<br />Driving Impact.
            </motion.h1>
            <motion.p custom={2} variants={fade} className="mt-6 text-lg text-white/75 max-w-xl leading-relaxed">
              CEC Connect is the home of the African American Women Trucking Association's community engagement — where ambassadors and volunteers build opportunity across trucking, transportation, and workforce development.
            </motion.p>
            <motion.div custom={3} variants={fade} className="mt-8 flex flex-wrap gap-3">
              <Button data-testid="hero-apply-btn" onClick={() => navigate("/apply")} className="rounded-full bg-brand-magenta hover:bg-brand-pink text-white h-12 px-7 text-base">
                Apply Now <ArrowRight size={18} className="ml-1" />
              </Button>
              <Button data-testid="hero-inquiry-btn" variant="outline" onClick={() => navigate("/contact")} className="rounded-full h-12 px-7 text-base bg-brand-magenta/15 border-2 border-brand-pink text-white hover:bg-brand-pink hover:border-brand-pink">
                Submit an Inquiry
              </Button>
              <Button data-testid="hero-login-btn" variant="ghost" onClick={() => navigate("/login")} className="rounded-full h-12 px-6 text-base text-white hover:bg-white/10">
                Member Login
              </Button>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Stats */}
      <section className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 py-10 grid grid-cols-2 md:grid-cols-4 gap-6">
          {[{ v: s.ambassadors ?? 0, l: "State Ambassadors", i: Award }, { v: s.states ?? 0, l: "States Represented", i: MapPin }, { v: s.volunteers ?? 0, l: "Active Volunteers", i: Users }, { v: s.events ?? 0, l: "Community Events", i: Calendar }].map((x, idx) => (
            <div key={idx} className="text-center">
              <x.i className="mx-auto text-brand-magenta mb-2" size={22} />
              <div className="font-head text-3xl md:text-4xl font-extrabold text-brand-navy">{x.v}</div>
              <div className="text-xs text-slate-500 font-medium mt-1">{x.l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* About the CEC */}
      <section className="max-w-7xl mx-auto px-4 py-20 grid lg:grid-cols-12 gap-12 items-center">
        <div className="lg:col-span-7">
          <SectionHeading eyebrow="Who We Are" title="The Community Engagement Committee" subtitle="The CEC is the outreach arm of AAWTA — mobilizing State Ambassadors and Volunteers to expand access, education, and opportunity for African American women in trucking and logistics." />
          <div className="grid sm:grid-cols-2 gap-4 mt-8">
            {focus.map((f) => (
              <div key={f.label} className="flex items-center gap-3 p-4 bg-white border border-slate-200 rounded-xl">
                <div className="h-10 w-10 rounded-lg bg-brand-magenta/10 text-brand-magenta flex items-center justify-center"><f.icon size={18} /></div>
                <span className="font-medium text-slate-700 text-sm">{f.label}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="lg:col-span-5 relative">
          <img src={IMG.driver3} alt="Ambassador" className="rounded-2xl w-full h-80 object-cover" />
          <div className="absolute -bottom-5 -left-5 bg-brand-magenta text-white p-5 rounded-xl shadow-lg max-w-[200px] hidden md:block">
            <p className="font-head font-bold text-lg">Led by women, for the community.</p>
          </div>
        </div>
      </section>

      {/* Ways to engage */}
      <section className="bg-[#FAF5FB] py-20">
        <div className="max-w-7xl mx-auto px-4">
          <SectionHeading center eyebrow="Get Involved" title="Ways to Support the CEC" />
          <div className="grid md:grid-cols-3 gap-6 mt-12">
            {ways.map((w, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }}
                className="bg-white border border-slate-200 rounded-2xl p-7 hover:-translate-y-1 hover:shadow-lg transition-all">
                <div className="h-12 w-12 rounded-xl bg-brand-navy text-white flex items-center justify-center mb-4"><w.icon size={22} /></div>
                <h3 className="font-head font-bold text-lg text-brand-navy">{w.title}</h3>
                <p className="text-slate-600 text-sm mt-2 leading-relaxed">{w.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Spotlights */}
      {data.spotlights?.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 py-20">
          <SectionHeading eyebrow="Meet Our Leaders" title="State Ambassador Spotlights" />
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 mt-10">
            {data.spotlights.map((m) => (
              <div key={m.id} className="bg-white border border-slate-200 rounded-2xl overflow-hidden hover:shadow-lg transition-shadow">
                <div className="h-44 bg-brand-navy/5">{m.photo ? <img src={`${API}/public/files/${m.photo}`} alt={m.name} className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center text-brand-navy/20"><Award size={48} /></div>}</div>
                <div className="p-4">
                  <h4 className="font-head font-bold text-brand-navy">{m.name}</h4>
                  <p className="text-xs text-brand-magenta font-semibold">{m.state} State Ambassador</p>
                  <p className="text-sm text-slate-500 mt-2 line-clamp-2">{m.bio}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Announcements + Events */}
      <section className="bg-brand-navy-dark py-20">
        <div className="max-w-7xl mx-auto px-4 grid lg:grid-cols-2 gap-10">
          <div>
            <SectionHeading light eyebrow="Latest News" title="Public Announcements" />
            <div className="mt-6 space-y-3">
              {(data.announcements?.length ? data.announcements : [{ title: "Welcome to CEC Connect", message: "Our new community engagement portal is live. Apply to become a State Ambassador today!", created_at: new Date().toISOString() }]).map((a, i) => (
                <div key={i} className="bg-white/5 border border-white/10 rounded-xl p-4 flex gap-3">
                  <Megaphone className="text-brand-pink shrink-0" size={20} />
                  <div><p className="font-semibold text-white">{a.title}</p><p className="text-sm text-white/60 line-clamp-2">{a.message}</p></div>
                </div>
              ))}
            </div>
          </div>
          <div>
            <SectionHeading light eyebrow="Save the Date" title="Upcoming Events" />
            <div className="mt-6 space-y-3">
              {(data.events?.length ? data.events : [{ name: "CEC Ambassador Orientation", date: "", location: "Virtual" }]).map((e, i) => (
                <div key={i} className="bg-white/5 border border-white/10 rounded-xl p-4 flex gap-3">
                  <Calendar className="text-brand-pink shrink-0" size={20} />
                  <div><p className="font-semibold text-white">{e.name}</p><p className="text-sm text-white/60">{e.date ? new Date(e.date).toLocaleDateString() : "Date TBA"} · {e.location || "Location TBA"}</p></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-7xl mx-auto px-4 py-20 text-center">
        <h2 className="font-head text-3xl md:text-4xl font-extrabold text-brand-navy">Ready to make an impact?</h2>
        <p className="text-slate-600 mt-3 max-w-xl mx-auto">Join a growing network of women driving change in trucking and their communities.</p>
        <div className="mt-7 flex flex-wrap gap-3 justify-center">
          <Button onClick={() => navigate("/apply")} className="rounded-full bg-brand-magenta hover:bg-brand-pink h-12 px-7">Apply Now <ArrowRight size={18} className="ml-1" /></Button>
          <Button variant="outline" onClick={() => navigate("/directory")} className="rounded-full h-12 px-7 border-brand-navy text-brand-navy hover:bg-brand-navy hover:text-white">View Ambassador Directory</Button>
        </div>
      </section>
    </PublicLayout>
  );
}
