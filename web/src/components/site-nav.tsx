"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Employees" },
  { href: "/direct-deposits", label: "Direct deposits" },
  { href: "/deductions", label: "Deductions" },
  { href: "/payroll", label: "Payroll" },
  { href: "/company", label: "Company" },
  { href: "/issues", label: "Issues" },
];

export function SiteNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-8 flex gap-1 text-sm">
      {LINKS.map(({ href, label }) => {
        const active =
          pathname === href || pathname === `${href}/` || (href !== "/" && pathname.startsWith(`${href}/`));
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 font-medium ${
              active ? "bg-neutral-900 text-white" : "text-neutral-600 hover:bg-neutral-200/60"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
