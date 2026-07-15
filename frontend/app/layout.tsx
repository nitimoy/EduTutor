import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SessionProvider } from "@/lib/SessionContext";
import { AuthProvider } from "@/lib/AuthContext";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "EduTutor — NCERT Class 12 AI Tutor",
  description: "AI-powered tutor for NCERT Class 12 Mathematics, Physics and Chemistry.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-slate-950 text-slate-50 antialiased`}>
        <AuthProvider>
          <SessionProvider>
            {children}
          </SessionProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
