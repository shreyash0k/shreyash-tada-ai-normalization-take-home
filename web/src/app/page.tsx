"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/issues");
  }, [router]);
  return (
    <p className="text-sm text-neutral-500">
      <Link href="/issues" className="underline">
        Continue to issues
      </Link>
    </p>
  );
}
