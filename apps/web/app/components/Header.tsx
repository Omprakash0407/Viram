"use client";

import { ChevronRight, Loader2, LogOut, MessageCircle, User } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "@/lib/session";

const navLinks = [
  { href: "/", label: "Home" },
  { href: "/plan", label: "Plan Trip" },
  { href: "/explore", label: "Explore" },
  { href: "/about", label: "About" },
];

export default function Header() {
  const { user, loading, signOut } = useSession();
  const pathname = usePathname();

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
            <>
              <span
                className="max-w-[16ch] truncate text-sm font-medium text-ink/80"
                title={user.email}
              >
                {user.display_name}
              </span>
              <button
                type="button"
                onClick={() => void signOut()}
                className="flex items-center gap-2 rounded-full bg-white px-4 py-2.5 text-sm font-medium text-ink shadow-sm transition-colors hover:bg-cream-dark"
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
                Sign out
              </button>
            </>
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
          <button
            type="button"
            aria-label="Chat with us"
            className="hidden h-11 w-11 items-center justify-center rounded-full bg-forest text-white transition-colors hover:bg-forest-dark sm:flex"
          >
            <MessageCircle className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
