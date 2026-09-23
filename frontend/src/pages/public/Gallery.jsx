import React, { useEffect, useState } from "react";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading, EmptyState, Loading } from "@/components/shared";
import { api, API } from "@/auth";
import { Images, MapPin, Calendar, X } from "lucide-react";

export default function Gallery() {
  const [items, setItems] = useState(null);
  const [active, setActive] = useState(null);
  useEffect(() => { api.get("/public/gallery").then((r) => setItems(r.data)).catch(() => setItems([])); }, []);

  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-16">
        <div className="max-w-7xl mx-auto px-4">
          <SectionHeading light eyebrow="Community Impact" title="Event Photo Gallery" subtitle="Moments from CEC community events, outreach days, and programs across the country — captured by our State Ambassadors." />
        </div>
      </section>
      <section className="max-w-7xl mx-auto px-4 py-16">
        {items === null ? <Loading /> : items.length === 0 ? (
          <EmptyState icon={Images} title="Gallery coming soon" subtitle="Approved event photos submitted by ambassadors will appear here." />
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4" data-testid="gallery-grid">
            {items.map((it, i) => (
              <button key={`${it.photo_id}-${i}`} onClick={() => setActive(it)} data-testid={`gallery-item-${i}`}
                className="group relative rounded-xl overflow-hidden aspect-square bg-brand-navy/5 focus:outline-none focus:ring-2 focus:ring-brand-magenta">
                <div className="absolute inset-0 flex items-center justify-center text-brand-navy/20"><Images size={40} /></div>
                <img src={`${API}/public/files/${it.photo_id}?w=500`} loading="lazy" alt={it.event_name} onError={(e) => { e.currentTarget.style.display = "none"; }} className="relative w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
                <div className="absolute inset-0 bg-gradient-to-t from-brand-navy-dark/85 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-3">
                  <div className="text-left text-white">
                    {it.caption && <p className="text-xs text-white/90 mb-1 line-clamp-2">“{it.caption}”</p>}
                    <p className="font-head font-semibold text-sm leading-tight">{it.event_name}</p>
                    <p className="text-[11px] text-white/80 flex items-center gap-1"><MapPin size={11} /> {it.state || "—"}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {active && (
        <div className="fixed inset-0 z-[60] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setActive(null)} data-testid="gallery-lightbox">
          <div className="max-w-4xl w-full bg-white rounded-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="relative bg-black">
              <img src={`${API}/public/files/${active.photo_id}`} alt={active.event_name} className="w-full max-h-[70vh] object-contain" />
              <button onClick={() => setActive(null)} data-testid="gallery-close" className="absolute top-3 right-3 h-9 w-9 rounded-full bg-white/90 flex items-center justify-center hover:bg-white"><X size={18} /></button>
            </div>
            <div className="p-5">
              <h3 className="font-head font-bold text-xl text-brand-navy">{active.event_name}</h3>
              {active.caption && <p className="text-brand-magenta font-medium mt-1">“{active.caption}”</p>}
              <div className="flex flex-wrap gap-4 text-sm text-slate-500 mt-1">
                {active.state && <span className="flex items-center gap-1"><MapPin size={14} /> {active.state}</span>}
                {active.date && <span className="flex items-center gap-1"><Calendar size={14} /> {new Date(active.date).toLocaleDateString()}</span>}
              </div>
              {active.highlights && <p className="text-slate-600 mt-3">{active.highlights}</p>}
            </div>
          </div>
        </div>
      )}
    </PublicLayout>
  );
}
