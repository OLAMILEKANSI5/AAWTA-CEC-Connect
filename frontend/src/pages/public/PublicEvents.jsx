import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading, Loading, EmptyState } from "@/components/shared";
import { EventCard } from "@/components/EventCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/auth";
import { EVENT_CATEGORIES, EVENT_FORMATS, EVENT_CAT_DOT, US_STATES } from "@/lib/constants";
import { ChevronLeft, ChevronRight, Search, CalendarDays, List, Calendar } from "lucide-react";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export default function PublicEvents() {
  const navigate = useNavigate();
  const [events, setEvents] = useState(null);
  const [view, setView] = useState("calendar");
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth());
  const [year, setYear] = useState(now.getFullYear());
  const [q, setQ] = useState(""); const [cat, setCat] = useState(""); const [fmt, setFmt] = useState(""); const [st, setSt] = useState("");

  const localDate = (s) => new Date(s + "T00:00");
  const load = () => {
    const p = new URLSearchParams();
    if (q) p.set("q", q); if (cat) p.set("category", cat); if (fmt) p.set("format", fmt); if (st) p.set("state", st);
    api.get(`/public/events?${p}`).then((r) => setEvents(r.data)).catch(() => setEvents([]));
  };
  useEffect(() => { const t = setTimeout(load, 300); return () => clearTimeout(t); /* eslint-disable-next-line */ }, [q, cat, fmt, st]);

  const byDay = useMemo(() => {
    const m = {};
    (events || []).forEach((e) => { if (!e.date) return; const d = localDate(e.date); if (d.getMonth() === month && d.getFullYear() === year) { const k = d.getDate(); (m[k] = m[k] || []).push(e); } });
    return m;
  }, [events, month, year]);

  const upcoming = (events || []).filter((e) => e.date && localDate(e.date) >= new Date(now.toDateString())).slice(0, 6);
  const first = new Date(year, month, 1).getDay();
  const days = new Date(year, month + 1, 0).getDate();
  const prev = () => { if (month === 0) { setMonth(11); setYear(year - 1); } else setMonth(month - 1); };
  const next = () => { if (month === 11) { setMonth(0); setYear(year + 1); } else setMonth(month + 1); };
  const years = Array.from({ length: 3 }, (_, i) => now.getFullYear() + i);

  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-14">
        <div className="max-w-7xl mx-auto px-4">
          <SectionHeading light eyebrow="What's Happening" title="AAWTA CEC Events Calendar" subtitle="Discover upcoming AAWTA community events, ambassador activities, workforce programs, workshops and networking opportunities. Select an event to learn more, register or purchase tickets." />
        </div>
      </section>
      <section className="max-w-7xl mx-auto px-4 py-10">
        <div className="flex flex-wrap gap-3 mb-6">
          <div className="relative flex-1 min-w-[200px]"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} /><Input data-testid="events-search" placeholder="Search by name, city, state or keyword…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" /></div>
          <select data-testid="filter-category" value={cat} onChange={(e) => setCat(e.target.value)} className="rounded-md border border-input px-3 text-sm bg-background"><option value="">All categories</option>{EVENT_CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select>
          <select data-testid="filter-format" value={fmt} onChange={(e) => setFmt(e.target.value)} className="rounded-md border border-input px-3 text-sm bg-background"><option value="">All formats</option>{EVENT_FORMATS.map((c) => <option key={c}>{c}</option>)}</select>
          <select data-testid="filter-state" value={st} onChange={(e) => setSt(e.target.value)} className="rounded-md border border-input px-3 text-sm bg-background"><option value="">All locations</option>{US_STATES.map((c) => <option key={c}>{c}</option>)}</select>
          <div className="flex rounded-md border border-input overflow-hidden">
            <button onClick={() => setView("calendar")} data-testid="view-calendar" className={`px-3 py-1.5 text-sm flex items-center gap-1 ${view === "calendar" ? "bg-brand-magenta text-white" : "bg-white text-slate-600"}`}><CalendarDays size={15} /> Calendar</button>
            <button onClick={() => setView("list")} data-testid="view-list" className={`px-3 py-1.5 text-sm flex items-center gap-1 ${view === "list" ? "bg-brand-magenta text-white" : "bg-white text-slate-600"}`}><List size={15} /> List</button>
          </div>
        </div>

        {events === null ? <Loading /> : view === "calendar" ? (
          <div className="bg-white border border-slate-200 rounded-2xl p-4" data-testid="calendar-grid">
            <div className="flex items-center justify-between mb-4">
              <Button variant="outline" size="sm" onClick={prev} data-testid="prev-month"><ChevronLeft size={16} /> Prev</Button>
              <div className="flex gap-2">
                <select value={month} onChange={(e) => setMonth(Number(e.target.value))} data-testid="month-select" className="rounded-md border border-input px-2 py-1 text-sm font-head font-semibold">{MONTHS.map((m, i) => <option key={m} value={i}>{m}</option>)}</select>
                <select value={year} onChange={(e) => setYear(Number(e.target.value))} data-testid="year-select" className="rounded-md border border-input px-2 py-1 text-sm font-head font-semibold">{years.map((y) => <option key={y} value={y}>{y}</option>)}</select>
              </div>
              <Button variant="outline" size="sm" onClick={next} data-testid="next-month">Next <ChevronRight size={16} /></Button>
            </div>
            <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-slate-400 mb-1">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => <div key={d}>{d}</div>)}</div>
            <div className="grid grid-cols-7 gap-1">
              {Array.from({ length: first }).map((_, i) => <div key={`e${i}`} />)}
              {Array.from({ length: days }).map((_, i) => {
                const day = i + 1; const evs = byDay[day] || [];
                return (
                  <div key={day} className="min-h-[70px] border border-slate-100 rounded-lg p-1 text-left">
                    <div className="text-xs text-slate-400">{day}</div>
                    {evs.slice(0, 3).map((e) => (
                      <button key={e.id} onClick={() => navigate(`/events/${e.id}`)} title={e.name} className="w-full text-left text-[10px] mt-0.5 px-1 py-0.5 rounded truncate text-white" style={{ background: EVENT_CAT_DOT[e.category] || "#64748b" }}>{e.name}</button>
                    ))}
                    {evs.length > 3 && <div className="text-[10px] text-slate-400">+{evs.length - 3} more</div>}
                  </div>
                );
              })}
            </div>
            <div className="flex flex-wrap gap-3 mt-4 pt-3 border-t border-slate-100">{EVENT_CATEGORIES.map((c) => <span key={c} className="flex items-center gap-1 text-[11px] text-slate-500"><span className="h-2.5 w-2.5 rounded-full" style={{ background: EVENT_CAT_DOT[c] }} /> {c}</span>)}</div>
          </div>
        ) : events.length === 0 ? <EmptyState icon={Calendar} title="No events found" subtitle="Try adjusting your search or filters." /> : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="events-list">
            {events.map((e) => <EventCard key={e.id} e={e} onOpen={(ev) => navigate(`/events/${ev.id}`)} />)}
          </div>
        )}

        {upcoming.length > 0 && (
          <div className="mt-14">
            <SectionHeading eyebrow="Don't Miss" title="Upcoming Events" />
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 mt-8">{upcoming.map((e) => <EventCard key={e.id} e={e} onOpen={(ev) => navigate(`/events/${ev.id}`)} />)}</div>
          </div>
        )}
      </section>
    </PublicLayout>
  );
}
