import Link from "next/link";

export type Crumb = { label: string; href?: string };

export function IssuesHeader({ crumbs }: { crumbs?: Crumb[] }) {
  return (
    <div className="mb-10">
      <h1 className="text-3xl font-semibold tracking-tight">Issues</h1>
      {crumbs ? (
        <nav aria-label="Breadcrumb" className="mt-2 flex flex-wrap items-center gap-2 text-sm text-neutral-500">
          {crumbs.map((crumb, index) => (
            <span key={crumb.label} className="flex items-center gap-2">
              {index > 0 && <span className="text-neutral-300">/</span>}
              {crumb.href ? (
                <Link
                  href={crumb.href}
                  className="text-neutral-900 underline decoration-neutral-300 underline-offset-4 hover:decoration-neutral-900"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span aria-current="page">{crumb.label}</span>
              )}
            </span>
          ))}
        </nav>
      ) : (
        <p className="mt-2 text-sm text-neutral-500">
          Everything normalization flagged, per employee. Choose a provider to see its clients.
        </p>
      )}
    </div>
  );
}
