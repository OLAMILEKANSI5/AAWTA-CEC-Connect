import React from "react";
import { PublicLayout } from "@/components/PublicLayout";
import { SectionHeading } from "@/components/shared";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

const FAQS = [
  { q: "What is the CEC?", a: "The Community Engagement Committee (CEC) is the outreach arm of the African American Women Trucking Association (AAWTA), mobilizing State Ambassadors and Volunteers to drive community impact." },
  { q: "How do I become a State Ambassador?", a: "Complete the State Ambassador application on the Apply page. Our team reviews every submission and follows up regarding next steps." },
  { q: "Do I need to be an AAWTA member to volunteer?", a: "No. Anyone passionate about the mission can apply to volunteer. Membership is encouraged but not required." },
  { q: "Does applying give me portal access?", a: "No. Submitting an application does not automatically grant portal access. Access is granted only after approval or a manual invitation from AAWTA leadership." },
  { q: "How do I log into the member portal?", a: "Use the 'Continue with Google' button on the login page. Your Google email must match an approved or invited address." },
  { q: "What happens after I submit a form?", a: "You'll receive a confirmation email with a reference number, and our team is notified. We review submissions and reach out with updates." },
  { q: "How can my organization partner with the CEC?", a: "Use the Contact / Learn More form and select 'Community partnership' or 'Sponsorship' as your inquiry type." },
];

export default function FAQ() {
  return (
    <PublicLayout>
      <section className="bg-brand-navy-dark text-white py-16">
        <div className="max-w-7xl mx-auto px-4"><SectionHeading light eyebrow="Questions" title="Frequently Asked Questions" /></div>
      </section>
      <section className="max-w-3xl mx-auto px-4 py-16">
        <Accordion type="single" collapsible className="space-y-3">
          {FAQS.map((f, i) => (
            <AccordionItem key={i} value={`item-${i}`} className="bg-white border border-slate-200 rounded-xl px-5">
              <AccordionTrigger className="font-head font-semibold text-brand-navy hover:no-underline text-left">{f.q}</AccordionTrigger>
              <AccordionContent className="text-slate-600">{f.a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </section>
    </PublicLayout>
  );
}
