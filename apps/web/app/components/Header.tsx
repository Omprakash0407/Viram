"use client";

import { ChevronRight, Loader2, LogOut, MapPinned, User } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useSession } from "@/lib/session";

const navLinks = [
  { href: "/", label: "Home" },
  { href: "/plan", label: "Plan Trip" },
  { href: "/explore", label: "Explore" },
  { href: "/partners", label: "Local Partners" },
  { href: "/trips", label: "My Trips" },
  { href: "/about", label: "About" },
];

export default function Header() {
  const { user, loading, signOut } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close the profile menu on outside click or Escape.
  useEffect(() => {
    if (!menuOpen) return;
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  async function handleSignOut() {
    setMenuOpen(false);
    await signOut();
    router.push("/");
  }

  return (
    <header className="bg-cream">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3" aria-label="VIRĀM home">
          <Image
            src="/images/logo-mark.png"
            alt="VIRĀM logo"
            width={96}
            height={60}
            priority
            className="h-auto w-24"
          />
        </Link>

        {/* Nav */}
        <nav className="hidden items-center gap-10 md:flex" aria-label="Main">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? "page" : undefined}
              className={`text-sm font-medium transition-colors hover:text-ink ${
                pathname === link.href ? "text-ink underline underline-offset-8" : "text-ink/80"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Right actions */}
        <div className="flex items-center gap-3">
          {loading ? (
            <span className="flex h-10 w-10 items-center justify-center">
              <Loader2 className="h-4 w-4 animate-spin text-ink/50" aria-hidden="true" />
            </span>
          ) : user ? (
            <div ref={menuRef} className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((v) => !v)}
                aria-expanded={menuOpen}
                aria-haspopup="menu"
                title={`${user.display_name} · account menu`}
                className="flex items-center gap-2 rounded-full bg-white py-1.5 pl-1.5 pr-3 shadow-sm transition-colors hover:bg-cream-dark"
              >
                {user.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element -- self-contained data URL avatar
                  <img
                    src={user.avatar_url}
                    alt=""
                    className="h-8 w-8 rounded-full object-cover ring-2 ring-forest/25"
                  />
                ) : (
                  <span
                    aria-hidden="true"
                    className="flex h-8 w-8 items-center justify-center rounded-full bg-forest/10 text-sm font-semibold text-forest"
                  >
                    {user.display_name.slice(0, 1).toUpperCase()}
                  </span>
                )}
                <span className="max-w-[14ch] truncate text-sm font-medium text-ink">
                  {user.display_name}
                </span>
                <ChevronRight
                  className={`h-4 w-4 text-ink/50 transition-transform ${menuOpen ? "rotate-90" : ""}`}
                  aria-hidden="true"
                />
              </button>

              {menuOpen ? (
                <div
                  role="menu"
                  aria-label="Account menu"
                  className="absolute right-0 top-full z-40 mt-2 w-52 overflow-hidden rounded-2xl bg-white py-1.5 shadow-xl ring-1 ring-ink/10"
                >
                  <p className="truncate px-4 pb-1 pt-1.5 text-[11px] text-ink/50" title={user.email}>
                    {user.email}
                  </p>
                  <Link
                    href="/profile"
                    role="menuitem"
                    onClick={() => setMenuOpen(false)}
                    className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-ink hover:bg-cream"
                  >
                    <User className="h-4 w-4 text-forest" aria-hidden="true" />
                    My profile
                  </Link>
                  <Link
                    href="/trips"
                    role="menuitem"
                    onClick={() => setMenuOpen(false)}
                    className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-ink hover:bg-cream"
                  >
                    <MapPinned className="h-4 w-4 text-forest" aria-hidden="true" />
                    My trips
                  </Link>
                  <div className="my-1 border-t border-ink/10" />
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => void handleSignOut()}
                    className="flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-sm text-red-700 hover:bg-red-50"
                  >
                    <LogOut className="h-4 w-4" aria-hidden="true" />
                    Sign out
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <Link
              href="/login"
              className="flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm font-medium text-ink shadow-sm transition-colors hover:bg-cream-dark"
            >
              <User className="h-4 w-4" aria-hidden="true" />
              Login or Sign Up
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
