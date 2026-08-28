import React from "react";
import { Badge } from "@/components/ui/badge";
import { STATUS_COLORS } from "@/lib/constants";
import { Loader2 } from "lucide-react";

export const StatusBadge = ({ status }) => (
  <Badge className={`${STATUS_COLORS[status] || "bg-slate-100 text-slate-600"} border-0 font-medium capitalize`}>{status}</Badge>
);

export const SectionHeading = ({ eyebrow, title, subtitle, light, center }) => (
  <div className={`${center ? "text-center mx-auto" : ""} max-w-2xl`}>
    {eyebrow && <div className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-brand-magenta mb-3">
      <span className="h-px w-6 bg-brand-magenta" />{eyebrow}
    </div>}
    <h2 className={`font-head text-3xl md:text-4xl font-extrabold ${light ? "text-white" : "text-brand-navy"}`}>{title}</h2>
    {subtitle && <p className={`mt-3 text-base ${light ? "text-white/70" : "text-slate-600"} leading-relaxed`}>{subtitle}</p>}
  </div>
);

export const StatCard = ({ label, value, icon: Icon, accent = "magenta", onClick }) => {
  const colors = { magenta: "text-brand-magenta bg-brand-magenta/10", navy: "text-brand-navy bg-brand-navy/10", amber: "text-amber-600 bg-amber-100", emerald: "text-emerald-600 bg-emerald-100", rose: "text-rose-600 bg-rose-100" };
  return (
    <div onClick={onClick} className={`bg-white border border-slate-200 rounded-xl p-4 flex items-center gap-4 transition-all ${onClick ? "cursor-pointer hover:-translate-y-0.5 hover:shadow-md" : ""}`}>
      {Icon && <div className={`h-11 w-11 rounded-lg flex items-center justify-center ${colors[accent]}`}><Icon size={20} /></div>}
      <div>
        <div className="text-2xl font-head font-bold text-brand-navy font-mono-data">{value}</div>
        <div className="text-xs text-slate-500 font-medium">{label}</div>
      </div>
    </div>
  );
};

export const Loading = ({ label = "Loading…" }) => (
  <div className="flex items-center justify-center py-20 text-slate-400 gap-2"><Loader2 className="animate-spin" size={20} /> {label}</div>
);

export const EmptyState = ({ icon: Icon, title, subtitle, action }) => (
  <div className="text-center py-16 border border-dashed border-slate-200 rounded-xl bg-white">
    {Icon && <Icon className="mx-auto text-slate-300 mb-3" size={40} />}
    <p className="font-head font-semibold text-slate-700">{title}</p>
    {subtitle && <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">{subtitle}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);

export const PageTitle = ({ title, subtitle, action }) => (
  <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
    <div>
      <h1 className="font-head text-2xl md:text-3xl font-extrabold text-brand-navy">{title}</h1>
      {subtitle && <p className="text-slate-500 text-sm mt-1">{subtitle}</p>}
    </div>
    {action}
  </div>
);
