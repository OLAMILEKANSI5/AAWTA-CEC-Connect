import React from "react";
import { LOGO_URL } from "@/lib/constants";

export const Logo = ({ className = "h-11 w-11", showText = true, dark = false }) => (
  <div className="flex items-center gap-3">
    <img src={LOGO_URL} alt="AAWTA logo" className={`${className} object-contain`} />
    {showText && (
      <div className="leading-tight">
        <div className={`font-head font-extrabold text-lg ${dark ? "text-white" : "text-brand-navy"}`}>
          CEC <span className="text-brand-magenta">Connect</span>
        </div>
        <div className={`text-[11px] font-medium ${dark ? "text-white/70" : "text-muted-foreground"}`}>
          AAWTA Community Engagement Portal
        </div>
      </div>
    )}
  </div>
);
