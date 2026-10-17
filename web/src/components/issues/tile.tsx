import Image from "next/image";
import Link from "next/link";
import type { TreeIssue } from "@/lib/issues";
import { IssueBadge } from "./issue-badge";

type Size = "normal" | "large";

export function tileClass(size: Size, interactive: boolean): string {
  const box = size === "large" ? "h-36 w-52" : "h-30 w-40";
  const hover = interactive ? "cursor-pointer transition hover:-translate-y-0.5 hover:shadow-md" : "";
  return `relative flex flex-col items-center justify-center rounded-xl border border-t-4 bg-white p-3 text-center shadow-sm ${box} ${hover}`;
}

export function TileContent({
  name,
  detail,
  issues,
  logo,
}: {
  name: string;
  detail?: string;
  issues?: TreeIssue[];
  logo?: string;
}) {
  return (
    <>
      {issues && <IssueBadge issues={issues} />}
      {logo ? (
        <Image src={logo} alt={name} width={140} height={32} className="h-7 w-auto max-w-full object-contain" />
      ) : (
        <span className="font-semibold leading-tight">{name}</span>
      )}
      {detail && <span className="mt-1 break-all font-mono text-[11px] text-neutral-400">{detail}</span>}
    </>
  );
}

export function Tile({
  name,
  detail,
  issues,
  accent,
  href,
  logo,
  size = "normal",
}: {
  name: string;
  detail?: string;
  issues?: TreeIssue[];
  accent: string;
  href?: string;
  logo?: string;
  size?: Size;
}) {
  const content = <TileContent name={name} detail={detail} issues={issues} logo={logo} />;
  const style = { borderTopColor: accent };
  if (href) {
    return (
      <Link href={href} className={tileClass(size, true)} style={style}>
        {content}
      </Link>
    );
  }
  return (
    <div className={tileClass(size, false)} style={style}>
      {content}
    </div>
  );
}
