import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { Providers } from "@/components/reviewintel/providers";

export const metadata: Metadata = {
  title: "ReviewLens - AI Product Review Intelligence",
  description:
    "Cross-platform product review intelligence: collects reviews from e-commerce marketplaces and social media, analyzes sentiment in English, Urdu and Roman Urdu, and compares feedback across platforms with an evidence-based verdict.",
  keywords: [
    "product reviews", "sentiment analysis", "Roman Urdu", "Urdu",
    "cross-platform comparison", "e-commerce", "Pakistan", "NLP",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased bg-background text-foreground">
        <Providers>{children}</Providers>
        <Toaster />
      </body>
    </html>
  );
}
