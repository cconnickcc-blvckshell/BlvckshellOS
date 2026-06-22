"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";

const LINKS = [
  { href: "/", label: "Home", glyph: "⌂" },
  { href: "/intake", label: "Intake", glyph: "◎" },
  { href: "/pipelines", label: "Pipelines", glyph: "⟁" },
  { href: "/ledger", label: "Ledger", glyph: "≣" },
  { href: "/doctrine", label: "Doctrine", glyph: "✦" },
  { href: "/memory", label: "Memory", glyph: "❖" },
  { href: "/observer", label: "Observer", glyph: "⊚" },
];

function NavContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <>
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
            onClick={onNavigate}
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
    </>
  );
}

export function SideNav() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed left-3 top-3 z-50 rounded-lg border border-border bg-surface/90 px-3 py-2 font-mono text-xs text-text-primary md:hidden"
        aria-label="Open navigation"
      >
        ☰
      </button>

      <nav className="nav-scan-border relative hidden w-14 shrink-0 flex-col gap-1 border-r border-border bg-surface/40 p-3 md:flex lg:w-52 lg:p-5">
        <NavContent />
      </nav>

      <AnimatePresence>
        {open && (
          <>
            <motion.button
              type="button"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/70 md:hidden"
              aria-label="Close navigation"
              onClick={() => setOpen(false)}
            />
            <motion.nav
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", damping: 28, stiffness: 320 }}
              className="nav-scan-border fixed inset-y-0 left-0 z-50 flex w-64 flex-col gap-1 border-r border-border bg-surface p-5 md:hidden"
            >
              <NavContent onNavigate={() => setOpen(false)} />
            </motion.nav>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
