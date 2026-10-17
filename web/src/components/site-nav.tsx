"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const COVERAGE = [
  { href: "/field-map", label: "Employees" },
  { href: "/field-map/direct-deposits", label: "Direct deposits" },
  { href: "/field-map/deductions", label: "Deductions" },
  { href: "/field-map/payroll", label: "Payroll" },
  { href: "/field-map/company", label: "Company" },
];

function isActive(pathname: string, href: string) {
  if (href === "/field-map") return pathname === "/field-map" || pathname === "/field-map/";
  return pathname === href || pathname === `${href}/` || pathname.startsWith(`${href}/`);
}

function pill(on: boolean) {
  return `rounded-md px-3 py-1.5 font-medium ${
    on ? "bg-neutral-900 text-white" : "text-neutral-600 hover:bg-neutral-200/60"
  }`;
}

function FieldMapMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-10">
      <rect x="3" y="3.5" width="5" height="3" rx="0.6" fill="currentColor" />
      <rect x="9.5" y="3.5" width="5" height="3" rx="0.6" fill="currentColor" />
      <rect x="16" y="3.5" width="5" height="3" rx="0.6" fill="currentColor" />
      <rect x="3" y="8.5" width="5" height="2.4" rx="0.5" fill="currentColor" opacity="0.55" />
      <rect x="9.5" y="8.5" width="5" height="2.4" rx="0.5" fill="currentColor" opacity="0.55" />
      <rect x="16" y="8.5" width="5" height="2.4" rx="0.5" fill="currentColor" opacity="0.55" />
      <rect x="3" y="12.7" width="5" height="2.4" rx="0.5" fill="currentColor" opacity="0.55" />
      <rect x="9.5" y="12.7" width="5" height="2.4" rx="0.5" fill="currentColor" opacity="0.55" />
      <rect x="16" y="12.7" width="5" height="2.4" rx="0.5" fill="currentColor" opacity="0.55" />
      <rect x="3" y="16.9" width="5" height="2.4" rx="0.5" fill="currentColor" opacity="0.55" />
      <rect x="9.5" y="16.9" width="5" height="2.4" rx="0.5" fill="currentColor" opacity="0.55" />
      <rect x="16" y="16.9" width="5" height="2.4" rx="0.5" fill="currentColor" opacity="0.55" />
    </svg>
  );
}

export function SiteNav() {
  const pathname = usePathname();
  const onFieldMap = pathname === "/field-map" || pathname.startsWith("/field-map/");
  if (!onFieldMap) {
    return (
      <Link
        href="/field-map"
        aria-label="Field map"
        className="fixed bottom-6 right-6 z-20 flex size-24 items-center justify-center rounded-full bg-neutral-900 text-white shadow-lg transition hover:-translate-y-0.5 hover:bg-neutral-700"
      >
        <FieldMapMark />
      </Link>
    );
  }
  return (
    <nav className="mb-8 flex gap-1 text-sm">
      {COVERAGE.map(({ href, label }) => {
        const on = isActive(pathname, href);
        return (
          <Link key={href} href={href} aria-current={on ? "page" : undefined} className={pill(on)}>
            {label}
          </Link>
        );
      })}
      <Link href="/issues" className={`${pill(false)} ml-auto`}>
        Issues
      </Link>
    </nav>
  );
}
