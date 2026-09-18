import { AuthPanel } from "@/app/components/AuthPanel";

export const metadata = { title: "Sign in — VIRĀM" };

export default function LoginPage() {
  return (
    <main className="mx-auto flex min-h-[70vh] w-full max-w-7xl items-center justify-center px-6 py-12">
      <AuthPanel purpose="Sign in to plan trips, save favourites and revisit your itineraries." />
    </main>
  );
}
