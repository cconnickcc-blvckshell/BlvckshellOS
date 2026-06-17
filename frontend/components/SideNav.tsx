"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const LINKS = [
  { href: "/", label: "Intake", glyph: "◎" },
  { href: "/pipelines", label: "Pipelines", glyph: "⟁" },
  { href: "/ledger", label: "Judgment Ledger", glyph: "≣" },
  { href: "/doctrine", label: "Doctrine", glyph: "✦" },
  { href: "/observer", label: "Observer", glyph: "⊚" },
];

export function SideNav() {
  const pathname = usePathname();
  return (
    <nav className="flex w-60 shrink-0 flex-col gap-1 border-r border-border bg-surface/40 p-5">
      <div className="mb-8 px-2">
        <div className="font-display text-lg font-semibold tracking-tight text-text-primary">
          BLVCKSHELL
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-text-secondary">
          harness
        </div>
      </div>
      {LINKS.map((link) => {
        const active =
          link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={clsx(
              "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
              active
                ? "bg-primary/15 text-text-primary"
                : "text-text-secondary hover:bg-surface hover:text-text-primary",
            )}
          >
            <span
              className={clsx(
                "font-mono text-base",
                active ? "text-active" : "text-text-secondary group-hover:text-active",
              )}
            >
              {link.glyph}
            </span>
            <span className="font-body">{link.label}</span>
          </Link>
        );
      })}
      <div className="mt-auto px-3 pt-6 font-mono text-[10px] leading-relaxed text-text-secondary">
        deep space
        <br />
        command center
      </div>
    </nav>
  );
}
