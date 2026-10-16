import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import "./globals.css";

export const metadata: Metadata = {
  title: "Field coverage",
  description: "How PrismHR, isolved and UKG Ready employee fields map into one canonical model.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-screen bg-neutral-50 font-sans text-neutral-900 antialiased">
        <main className="mx-auto max-w-7xl px-6 py-10">{children}</main>
      </body>
    </html>
  );
}
