"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const LINKS = [
  { href: "/", label: "Home", glyph: "⌂" },
  { href: "/intake", label: "Intake", glyph: "◎" },
  { href: "/pipelines", label: "Pipelines", glyph: "⟁" },
  { href: "/ledger", label: "Ledger", glyph: "≣" },
  { href: "/doctrine", label: "Doctrine", glyph: "✦" },
  { href: "/observer", label: "Observer", glyph: "⊚" },
];

export function SideNav() {
  const pathname = usePathname();
  return (
    <nav className="flex w-52 shrink-0 flex-col gap-1 border-r border-border bg-surface/40 p-4 lg:w-60 lg:p-5">
      <div className="mb-6 px-2 lg:mb-8">
        <div className="font-display text-base font-semibold tracking-tight text-text-primary lg:text-lg">
          BLVCKSHELL OS
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-secondary">
          command center
        </div>
      </div>
      {LINKS.map((link) => {
        const active =
          link.href === "/"
            ? pathname === "/"
            : pathname === link.href || pathname.startsWith(`${link.href}/`);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={clsx(
              "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
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
