"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS: { href: string; label: string; glyph: string }[] = [
  { href: "/", label: "Intake", glyph: "◎" },
  { href: "/pipeline", label: "Pipeline", glyph: "⌬" },
  { href: "/judgments", label: "Judgment Ledger", glyph: "▤" },
  { href: "/doctrine", label: "Doctrine", glyph: "✦" },
  { href: "/observer", label: "Observer", glyph: "❯" },
];

/** Left-rail navigation for the command interface. */
export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex h-full w-60 shrink-0 flex-col border-r border-border bg-surface/60 px-4 py-6">
      <Link href="/" className="mb-10 flex items-center gap-3 px-2">
        <span className="h-3 w-3 rounded-full bg-active shadow-[0_0_14px_rgba(168,85,247,0.8)]" />
        <span className="font-display text-lg font-semibold tracking-tight text-text-primary">
          BLVCKSHELL
        </span>
      </Link>
      <ul className="flex flex-1 flex-col gap-1">
        {LINKS.map((link) => {
          const active =
            link.href === "/"
              ? pathname === "/"
              : pathname.startsWith(link.href);
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                  active
                    ? "bg-primary/20 text-text-primary"
                    : "text-text-secondary hover:bg-border/40 hover:text-text-primary"
                }`}
              >
                <span className="w-4 text-center font-mono text-active">
                  {link.glyph}
                </span>
                <span className="font-display">{link.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
      <p className="px-3 font-mono text-[10px] uppercase tracking-widest text-text-secondary">
        agent harness · v0.1
      </p>
    </nav>
  );
}
