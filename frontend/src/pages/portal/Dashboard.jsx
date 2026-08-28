import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, Clock, CheckCircle2, Users, Calendar, Target, Megaphone, UserCheck, Award, ArrowRight, BookOpen, MessageSquare } from "lucide-react";
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { useAuth, api } from "@/auth";
import { StatCard, Loading, PageTitle } from "@/components/shared";
import { StatusBadge } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

const STAFF = ["super_admin", "director", "administrator"];

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isStaff = STAFF.includes(user?.role);
  const [stats, setStats] = useState(null);
  const [member, setMember] = useState(null);
  const [anns, setAnns] = useState([]);

  useEffect(() => {
    if (isStaff) api.get("/dashboard/stats").then((r) => setStats(r.data)).catch(() => {});
    else {
      api.get("/members/me").then((r) => setMember(r.data)).catch(() => setMember(false));
      api.get("/announcements").then((r) => setAnns(r.data)).catch(() => {});
    }
  }, [isStaff]);

  if (isStaff) {
    if (!stats) return <Loading />;
    const pieData = Object.entries(stats.by_type || {}).map(([k, v]) => ({ name: k, value: v }));
    const COLORS = ["#D6189B", "#2E3192", "#F4B400"];
    const barData = ["New", "Under Review", "Approved", "Waitlisted", "Declined"].map((s) => ({ name: s, count: stats.by_status?.[s] || 0 }));
    return (
      <div className="space-y-6">
        <PageTitle title={`Welcome back, ${user?.name?.split(" ")[0]}`} subtitle="Administrative command center" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="New Applications" value={stats.new_applications} icon={FileText} accent="magenta" onClick={() => navigate("/portal/applications?status=New")} />
          <StatCard label="Under Review" value={stats.under_review} icon={Clock} accent="amber" onClick={() => navigate("/portal/applications?status=Under Review")} />
          <StatCard label="Approved" value={stats.approved} icon={CheckCircle2} accent="emerald" />
          <StatCard label="Waitlisted" value={stats.waitlisted} icon={Users} accent="navy" />
          <StatCard label="Active Ambassadors" value={stats.active_ambassadors} icon={Award} accent="magenta" onClick={() => navigate("/portal/members?role=ambassador")} />
          <StatCard label="Active Volunteers" value={stats.active_volunteers} icon={UserCheck} accent="navy" onClick={() => navigate("/portal/members?role=volunteer")} />
          <StatCard label="Pending Events" value={stats.pending_events} icon={Calendar} accent="amber" onClick={() => navigate("/portal/events")} />
          <StatCard label="Overdue Goals" value={stats.overdue_goals} icon={Target} accent="rose" onClick={() => navigate("/portal/goals")} />
          <StatCard label="Incomplete Onboarding" value={stats.incomplete_onboarding} icon={Clock} accent="amber" />
          <StatCard label="Announcement Requests" value={stats.announcement_requests} icon={Megaphone} accent="magenta" onClick={() => navigate("/portal/announcements")} />
          <StatCard label="Declined" value={stats.declined} icon={FileText} accent="rose" />
          <StatCard label="Total Members" value={stats.total_members} icon={Users} accent="navy" />
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-head font-semibold text-brand-navy mb-3">Applications by Type</h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart><Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                {pieData.map((e, i) => <Cell key={i} fill={COLORS[i % 3]} />)}</Pie><Tooltip /></PieChart>
            </ResponsiveContainer>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-5 lg:col-span-2">
            <h3 className="font-head font-semibold text-brand-navy mb-3">Applications by Status</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={barData}><XAxis dataKey="name" fontSize={11} /><YAxis fontSize={11} allowDecimals={false} /><Tooltip /><Bar dataKey="count" fill="#D6189B" radius={[4, 4, 0, 0]} /></BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3"><h3 className="font-head font-semibold text-brand-navy">Recent Applications</h3><Button variant="ghost" size="sm" onClick={() => navigate("/portal/applications")}>View all <ArrowRight size={14} className="ml-1" /></Button></div>
            <div className="space-y-2">
              {stats.recent_applications?.map((a) => (
                <div key={a.id} onClick={() => navigate(`/portal/applications/${a.id}`)} className="flex items-center justify-between p-2.5 rounded-lg hover:bg-slate-50 cursor-pointer">
                  <div><p className="text-sm font-medium text-slate-800">{a.name}</p><p className="text-xs text-slate-400 font-mono-data">{a.ref} · {a.type}</p></div>
                  <StatusBadge status={a.status} />
                </div>
              ))}
              {!stats.recent_applications?.length && <p className="text-sm text-slate-400 py-4 text-center">No applications yet</p>}
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3"><h3 className="font-head font-semibold text-brand-navy">Upcoming Events</h3><Button variant="ghost" size="sm" onClick={() => navigate("/portal/events")}>View all <ArrowRight size={14} className="ml-1" /></Button></div>
            <div className="space-y-2">
              {stats.upcoming_events?.map((e) => (
                <div key={e.id} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50">
                  <Calendar size={18} className="text-brand-magenta" />
                  <div><p className="text-sm font-medium text-slate-800">{e.name}</p><p className="text-xs text-slate-400">{e.date ? new Date(e.date).toLocaleDateString() : "TBA"}</p></div>
                </div>
              ))}
              {!stats.upcoming_events?.length && <p className="text-sm text-slate-400 py-4 text-center">No upcoming events</p>}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Member dashboard
  const onboarding = member?.onboarding || [];
  const doneCount = onboarding.filter((o) => o.done).length;
  const pct = onboarding.length ? Math.round((doneCount / onboarding.length) * 100) : 0;
  const links = [
    { i: Target, t: "My Goals & Activity", to: "/portal/goals" },
    { i: BookOpen, t: "Resource Center", to: "/portal/resources" },
    { i: MessageSquare, t: "Messages", to: "/portal/messages" },
    { i: Calendar, t: "Events", to: "/portal/events" },
  ];
  return (
    <div className="space-y-6">
      <PageTitle title={`Welcome, ${user?.name?.split(" ")[0]}`} subtitle="Your CEC Connect member portal" />
      {member && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-head font-semibold text-brand-navy">Onboarding Progress</h3>
            <span className="text-sm font-mono-data font-bold text-brand-magenta">{pct}%</span>
          </div>
          <Progress value={pct} className="h-2.5" />
          <p className="text-sm text-slate-500 mt-2">{doneCount} of {onboarding.length} steps complete</p>
          <Button className="mt-4 rounded-full bg-brand-magenta hover:bg-brand-pink" onClick={() => navigate("/portal/onboarding")}>Continue Onboarding <ArrowRight size={16} className="ml-1" /></Button>
        </div>
      )}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {links.map((l) => (
          <div key={l.to} onClick={() => navigate(l.to)} className="bg-white border border-slate-200 rounded-xl p-5 cursor-pointer hover:-translate-y-1 hover:shadow-md transition-all">
            <div className="h-11 w-11 rounded-lg bg-brand-magenta/10 text-brand-magenta flex items-center justify-center mb-3"><l.i size={20} /></div>
            <p className="font-head font-semibold text-brand-navy">{l.t}</p>
          </div>
        ))}
      </div>
      <div className="bg-white border border-slate-200 rounded-xl p-5">
        <h3 className="font-head font-semibold text-brand-navy mb-3">Latest Announcements</h3>
        {anns.slice(0, 4).map((a) => (
          <div key={a.id} className="flex gap-3 p-2.5 border-b last:border-0 border-slate-100">
            <Megaphone size={18} className="text-brand-magenta shrink-0" /><div><p className="text-sm font-medium text-slate-800">{a.title}</p><p className="text-xs text-slate-500 line-clamp-2">{a.message}</p></div>
          </div>
        ))}
        {!anns.length && <p className="text-sm text-slate-400 py-4 text-center">No announcements</p>}
      </div>
    </div>
  );
}
