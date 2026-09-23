import React, { useEffect, useMemo, useState } from "react";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading, EmptyState, Loading } from "@/components/shared";
import { api, API } from "@/auth";
import { Award, MapPin, Linkedin, Instagram, Facebook, Users, Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";

export default function Directory() {
  const [members, setMembers] = useState(null);
  const [q, setQ] = useState("");
  const [stateF, setStateF] = useState("");
  const [focusF, setFocusF] = useState("");

  useEffect(() => { api.get("/public/directory").then((r) => setMembers(r.data)).catch(() => setMembers([])); }, []);

  const states = useMemo(() => [...new Set((members || []).map((m) => m.state).filter(Boolean))].sort(), [members]);
  const focuses = useMemo(() => [...new Set((members || []).flatMap((m) => m.focus_areas || []))].sort(), [members]);
  const filtered = useMemo(() => (members || []).filter((m) =>
    (!q || m.name?.toLowerCase().includes(q.toLowerCase())) &&
    (!stateF || m.state === stateF) &&
    (!focusF || (m.focus_areas || []).includes(focusF))
  ), [members, q, stateF, focusF]);
  const hasFilter = q || stateF || focusF;

  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-16">
        <div className="max-w-7xl mx-auto px-4"><SectionHeading light eyebrow="Our Network" title="State Ambassador Directory" subtitle="Meet the approved State Ambassadors representing AAWTA across the country. Search by name, state, or focus area to find your local ambassador." /></div>
      </section>
      <section className="max-w-7xl mx-auto px-4 py-16">
        {members === null ? <Loading /> : members.length === 0 ? (
          <EmptyState icon={Users} title="Directory coming soon" subtitle="Approved ambassadors who choose a public profile will appear here." />
        ) : (
          <>
            <div className="flex flex-wrap gap-3 mb-8">
              <div className="relative flex-1 min-w-[220px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                <Input data-testid="directory-search" placeholder="Search by name…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
              </div>
              <select data-testid="directory-state-filter" value={stateF} onChange={(e) => setStateF(e.target.value)} className="rounded-md border border-input px-3 text-sm bg-background">
                <option value="">All states</option>{states.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <select data-testid="directory-focus-filter" value={focusF} onChange={(e) => setFocusF(e.target.value)} className="rounded-md border border-input px-3 text-sm bg-background">
                <option value="">All focus areas</option>{focuses.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
              {hasFilter && <button onClick={() => { setQ(""); setStateF(""); setFocusF(""); }} data-testid="directory-clear" className="flex items-center gap-1 text-sm text-brand-magenta hover:underline"><X size={14} /> Clear</button>}
            </div>
            <p data-testid="directory-count" className="text-sm text-slate-500 mb-4">{filtered.length} ambassador{filtered.length !== 1 ? "s" : ""}{hasFilter ? " match your search" : ""}</p>
            {filtered.length === 0 ? <EmptyState icon={Search} title="No ambassadors match" subtitle="Try adjusting your filters." /> : (
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="directory-grid">
                {filtered.map((m) => (
                  <div key={m.id} className="bg-white border border-slate-200 rounded-2xl overflow-hidden hover:shadow-lg transition-shadow">
                    <div className="h-52 bg-brand-navy/5">{m.photo ? <img src={`${API}/public/files/${m.photo}?w=500`} loading="lazy" alt={m.name} className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center text-brand-navy/20"><Award size={56} /></div>}</div>
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
          </>
        )}
      </section>
    </PublicLayout>
  );
}
