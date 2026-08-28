import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, API } from "@/auth";
import { PageTitle, Loading } from "@/components/shared";
import { UploadButton } from "@/components/PortalUpload";
import { Button } from "@/components/ui/button";
import { Field, MultiChips } from "@/components/FormFields";
import { FOCUS_AREAS } from "@/lib/constants";

export default function MyProfile() {
  const [m, setM] = useState(null);
  const [busy, setBusy] = useState(false);
  const on = (k, v) => setM((p) => ({ ...p, [k]: v }));

  useEffect(() => { api.get("/members/me").then((r) => setM(r.data)).catch(() => setM(false)); }, []);

  const save = async () => {
    setBusy(true);
    try { await api.put(`/members/${m.id}`, m); toast.success("Profile saved"); } catch { toast.error("Save failed"); }
    setBusy(false);
  };

  if (m === null) return <Loading />;
  if (m === false) return <div className="text-slate-500">No member profile is linked to your account yet.</div>;

  return (
    <div className="space-y-5 max-w-3xl">
      <PageTitle title="My Profile" subtitle="Keep your information up to date" action={<Button onClick={save} disabled={busy} data-testid="save-profile-btn" className="rounded-full bg-brand-magenta hover:bg-brand-pink">{busy ? "Saving…" : "Save Changes"}</Button>} />
      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-5">
        <div className="flex items-center gap-4">
          <div className="h-20 w-20 rounded-full bg-brand-navy/10 overflow-hidden flex items-center justify-center text-brand-navy font-head text-2xl font-bold">
            {m.photo ? <img src={`${API}/files/${m.photo}/download`} alt="" className="w-full h-full object-cover" /> : m.name?.[0]}
          </div>
          <UploadButton testid="upload-headshot" category="headshot" accept="image/*" label="Upload headshot" onUploaded={(f) => on("photo", f.id)} />
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Phone" name="phone" value={m.phone} onChange={on} />
          <Field label="City" name="city" value={m.city} onChange={on} />
          <Field label="County" name="county" value={m.county} onChange={on} />
          <Field label="Company / organization" name="company" value={m.company} onChange={on} />
          <Field label="Job title" name="job_title" value={m.job_title} onChange={on} />
          <Field label="Membership status" name="membership_status" value={m.membership_status} onChange={on} />
          <Field label="LinkedIn" name="linkedin" value={m.linkedin} onChange={on} />
          <Field label="Facebook" name="facebook" value={m.facebook} onChange={on} />
          <Field label="Instagram" name="instagram" value={m.instagram} onChange={on} />
        </div>
        <Field label="Biography" name="bio" value={m.bio} onChange={on} textarea />
        <MultiChips label="Focus areas" options={FOCUS_AREAS} value={m.focus_areas || []} onChange={(v) => on("focus_areas", v)} />
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!m.public_profile} onChange={(e) => on("public_profile", e.target.checked)} className="accent-[#D6189B]" data-testid="profile-public-toggle" /> Make my profile visible in the public directory</label>
      </div>
    </div>
  );
}
