"use client";

import { useState } from "react";
import clsx from "clsx";
import { ChatPanel } from "@/components/ChatPanel";
import { CommandCenter } from "@/components/CommandCenter";

export default function HomePage() {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="relative flex h-full overflow-hidden">
      {/* Chat — full width on mobile, 40% on desktop */}
      <ChatPanel className="w-full border-r border-white/10 md:w-2/5" />

      {/* Command center — bottom drawer on mobile, 60% panel on desktop */}
      <CommandCenter
        className={clsx(
          "hidden md:flex md:w-3/5",
          drawerOpen &&
            "fixed inset-x-0 bottom-0 z-30 flex h-[72vh] w-full rounded-t-2xl border-t border-white/10 shadow-2xl md:relative md:inset-auto md:h-full md:rounded-none md:border-t-0 md:shadow-none",
        )}
      />

      {/* Mobile drawer toggle */}
      <button
        type="button"
        onClick={() => setDrawerOpen((v) => !v)}
        className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary font-mono text-lg text-white shadow-lg shadow-primary/30 md:hidden"
        aria-label={drawerOpen ? "Close command center" : "Open command center"}
      >
        {drawerOpen ? "×" : "◎"}
      </button>

      {/* Mobile drawer backdrop */}
      {drawerOpen && (
        <button
          type="button"
          aria-label="Close"
          className="fixed inset-0 z-20 bg-black/60 md:hidden"
          onClick={() => setDrawerOpen(false)}
        />
      )}
    </div>
  );
}
