import React, { useEffect, useState } from "react";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading, EmptyState, Loading } from "@/components/shared";
import { api, API } from "@/auth";
import { Award, MapPin, Linkedin, Instagram, Facebook, Users } from "lucide-react";

export default function Directory() {
  const [members, setMembers] = useState(null);
  useEffect(() => { api.get("/public/directory").then((r) => setMembers(r.data)).catch(() => setMembers([])); }, []);
  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-16">
        <div className="max-w-7xl mx-auto px-4"><SectionHeading light eyebrow="Our Network" title="State Ambassador Directory" subtitle="Meet the approved State Ambassadors representing AAWTA across the country." /></div>
      </section>
      <section className="max-w-7xl mx-auto px-4 py-16">
        {members === null ? <Loading /> : members.length === 0 ? (
          <EmptyState icon={Users} title="Directory coming soon" subtitle="Approved ambassadors who choose a public profile will appear here." />
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="directory-grid">
            {members.map((m) => (
              <div key={m.id} className="bg-white border border-slate-200 rounded-2xl overflow-hidden hover:shadow-lg transition-shadow">
                <div className="h-52 bg-brand-navy/5">{m.photo ? <img src={`${API}/public/files/${m.photo}`} alt={m.name} className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center text-brand-navy/20"><Award size={56} /></div>}</div>
                <div className="p-5">
                  <h3 className="font-head font-bold text-lg text-brand-navy">{m.name}</h3>
                  <p className="text-brand-magenta text-sm font-semibold flex items-center gap-1"><MapPin size={13} /> {m.state} · {m.title}</p>
                  {m.focus_areas?.length > 0 && <div className="flex flex-wrap gap-1.5 mt-3">{m.focus_areas.slice(0, 3).map((f) => <span key={f} className="text-[11px] px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full">{f}</span>)}</div>}
                  <p className="text-sm text-slate-500 mt-3 line-clamp-3">{m.bio}</p>
                  <div className="flex gap-2 mt-4">
                    {m.linkedin && <a href={m.linkedin} target="_blank" rel="noreferrer" className="text-slate-400 hover:text-brand-navy"><Linkedin size={18} /></a>}
                    {m.instagram && <a href={m.instagram} target="_blank" rel="noreferrer" className="text-slate-400 hover:text-brand-magenta"><Instagram size={18} /></a>}
                    {m.facebook && <a href={m.facebook} target="_blank" rel="noreferrer" className="text-slate-400 hover:text-brand-navy"><Facebook size={18} /></a>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </PublicLayout>
  );
}
