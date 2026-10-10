import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

import { BrandMark } from "@/components/brand-mark";
import { SiteNav } from "@/components/site-nav";
import { LangProvider, LangToggle } from "@/lib/i18n";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "LLM Bench · Inference Load Testing",
  description:
    "Benchmark LLM inference from one API: TTFT, throughput, TPOT and concurrency behavior",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <LangProvider>
          <div className="app-canvas flex min-h-dvh flex-col">
            <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-md supports-[filter]:bg-background/65">
              <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 lg:px-6">
                <Link
                  href="/"
                  className="flex items-center gap-2.5 rounded-md font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label="LLM Bench home"
                >
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                    <BrandMark className="h-5 w-5" />
                  </span>
                  <span className="flex flex-col leading-none">
                    <span className="text-sm">LLM Bench</span>
                    <span className="text-[10px] font-normal text-muted-foreground">
                      Inference benchmark console
                    </span>
                  </span>
                </Link>
                <div className="mx-1 h-5 w-px bg-border" aria-hidden />
                <SiteNav />
                <LangToggle />
              </div>
            </header>

            <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 lg:px-6">
              {children}
            </main>
          </div>
        </LangProvider>
      </body>
    </html>
  );
}
