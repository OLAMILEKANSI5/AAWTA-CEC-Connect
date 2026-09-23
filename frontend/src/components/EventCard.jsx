import React from "react";
import { Calendar, MapPin, Clock, Ticket, ArrowRight, Image as ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { API } from "@/auth";
import { EVENT_CAT_COLORS } from "@/lib/constants";

export const regLabel = (e) => {
  if (e.registration_status === "closed") return { label: "Registration Closed", disabled: true };
  if (e.registration_status === "waitlist") return { label: "Join Waitlist", disabled: false };
  if (e.format === "Virtual") return { label: e.is_paid ? "Purchase Tickets" : "Register for Event", disabled: false };
  return { label: e.is_paid ? "Purchase Tickets" : "Register for Event", disabled: false };
};

export const EventCard = ({ e, onOpen }) => {
  const cat = EVENT_CAT_COLORS[e.category] || "bg-slate-100 text-slate-600";
  const loc = e.format === "Virtual" ? "Virtual" : [e.city, e.state].filter(Boolean).join(", ") || e.location || "Location TBA";
  const reg = regLabel(e);
  return (
    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden hover:shadow-lg transition-shadow flex flex-col" data-testid={`event-card-${e.id}`}>
      <div className="h-36 bg-brand-navy/5 relative">
        {e.image_file_id ? <img src={`${API}/public/files/${e.image_file_id}?w=500`} loading="lazy" alt={e.name} className="w-full h-full object-cover" onError={(ev) => { ev.currentTarget.style.display = "none"; }} /> : <div className="w-full h-full flex items-center justify-center text-brand-navy/20"><Calendar size={40} /></div>}
        <span className={`absolute top-3 left-3 text-[11px] font-semibold px-2 py-0.5 rounded-full ${cat}`}>{e.category || "Event"}</span>
        <span className={`absolute top-3 right-3 text-[11px] font-semibold px-2 py-0.5 rounded-full ${e.is_paid ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>{e.is_paid ? (e.price ? e.price : "Paid") : "Free"}</span>
      </div>
      <div className="p-5 flex-1 flex flex-col">
        <h3 className="font-head font-bold text-brand-navy leading-tight">{e.name}</h3>
        <div className="text-sm text-slate-500 mt-2 space-y-1">
          <p className="flex items-center gap-1.5"><Calendar size={13} className="text-brand-magenta" /> {e.date ? new Date(e.date + "T00:00").toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "Date TBA"}{e.start_time ? <span className="flex items-center gap-1 ml-1"><Clock size={12} /> {e.start_time}</span> : null}</p>
          <p className="flex items-center gap-1.5"><MapPin size={13} className="text-brand-magenta" /> {loc}</p>
        </div>
        {e.description && <p className="text-sm text-slate-500 mt-2 line-clamp-2 flex-1">{e.description}</p>}
        <div className="flex gap-2 mt-4">
          <Button size="sm" variant="outline" onClick={() => onOpen(e)} data-testid={`event-details-${e.id}`} className="flex-1">View Details</Button>
          <Button size="sm" onClick={() => onOpen(e)} disabled={reg.disabled} data-testid={`event-register-${e.id}`} className="flex-1 bg-brand-magenta hover:bg-brand-pink"><Ticket size={13} className="mr-1" /> {reg.label.split(" ")[0]}</Button>
        </div>
      </div>
    </div>
  );
};
