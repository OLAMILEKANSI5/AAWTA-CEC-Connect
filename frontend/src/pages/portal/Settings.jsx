import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/auth";
import { PageTitle, Loading } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/FormFields";

export default function Settings() {
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  const on = (k, v) => setS((p) => ({ ...p, [k]: v }));
  useEffect(() => { api.get("/settings").then((r) => setS(r.data)).catch(() => {}); }, []);
  const save = async () => { setBusy(true); try { await api.put("/settings", s); toast.success("Settings saved"); } catch { toast.error("Failed"); } setBusy(false); };
  if (!s) return <Loading />;

  return (
    <div className="space-y-5 max-w-2xl">
      <PageTitle title="Portal Settings" subtitle="Editable organization details, links & contact info" action={<Button onClick={save} disabled={busy} data-testid="save-settings-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink">{busy ? "Saving…" : "Save Settings"}</Button>} />
      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <Field label="Power Lab address" name="address" value={s.address} onChange={on} />
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Main telephone" name="phone" value={s.phone} onChange={on} />
          <Field label="Contact email" name="email" value={s.email} onChange={on} />
        </div>
        <Field label="AAWTA website" name="website" value={s.website} onChange={on} />
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Google Calendar link" name="calendar_link" value={s.calendar_link} onChange={on} />
          <Field label="Slack workspace link" name="slack_link" value={s.slack_link} onChange={on} />
        </div>
        <Field label="Membership link" name="membership_link" value={s.membership_link} onChange={on} />
      </div>
    </div>
  );
}
