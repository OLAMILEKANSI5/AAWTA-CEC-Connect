import React, { useEffect, useState } from "react";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading } from "@/components/shared";
import { api } from "@/auth";
import { Globe, Calendar, MessageSquare, BookOpen, ExternalLink, UserPlus } from "lucide-react";

export default function ResourcesPublic() {
  const [settings, setSettings] = useState({});
  useEffect(() => { api.get("/settings").then((r) => setSettings(r.data)).catch(() => {}); }, []);
  const cards = [
    { i: Globe, t: "AAWTA Main Website", d: "Learn about the association and membership.", url: settings.website },
    { i: Calendar, t: "AAWTA Calendar", d: "See upcoming AAWTA and CEC events.", url: settings.calendar_link },
    { i: MessageSquare, t: "Access CEC Slack Workspace", d: "Connect with the community (members).", url: settings.slack_link },
    { i: UserPlus, t: "AAWTA Membership", d: "Join the African American Women Trucking Association.", url: settings.membership_link },
  ];
  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-16">
        <div className="max-w-7xl mx-auto px-4"><SectionHeading light eyebrow="Helpful Links" title="Resources" subtitle="Quick access to AAWTA tools, community spaces, and membership. Members unlock the full resource center inside the portal." /></div>
      </section>
      <section className="max-w-7xl mx-auto px-4 py-16 grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {cards.map((c, i) => (
          <a key={i} href={c.url || "#"} target="_blank" rel="noopener noreferrer" data-testid={`public-resource-${i}`}
            className="bg-white border border-slate-200 rounded-2xl p-6 hover:-translate-y-1 hover:shadow-lg transition-all group">
            <div className="h-11 w-11 rounded-xl bg-brand-magenta/10 text-brand-magenta flex items-center justify-center mb-4"><c.i size={20} /></div>
            <h3 className="font-head font-bold text-brand-navy flex items-center gap-1">{c.t} <ExternalLink size={14} className="opacity-0 group-hover:opacity-100 transition-opacity" /></h3>
            <p className="text-slate-600 text-sm mt-2">{c.d}</p>
          </a>
        ))}
      </section>
    </PublicLayout>
  );
}
