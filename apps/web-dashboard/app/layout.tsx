import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "loom — the upskilling dashboard",
  description:
    "The operator-facing surface for loom. Watch the upskilling loop happen and act on promotion candidates.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen flex flex-col">
          <header className="border-b border-loom-700 bg-loom-900">
            <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
              <h1 className="text-xl font-semibold tracking-tight">loom</h1>
              <nav className="flex gap-4 text-sm text-loom-100">
                <a href="/" className="hover:text-white">
                  Home
                </a>
                <a href="/candidates" className="hover:text-white">
                  Candidates
                </a>
                <a href="/dashboard" className="hover:text-white">
                  Observability
                </a>
              </nav>
            </div>
          </header>
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-8">
            {children}
          </main>
          <footer className="border-t border-loom-700 text-xs text-loom-500 py-4 text-center">
            loom — dev environment
          </footer>
        </div>
      </body>
    </html>
  );
}
