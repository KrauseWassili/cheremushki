import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Header from "@/components/header";
import Footer from "@/components/footer";
import {
  APP_SCROLL_CONTAINER_ID,
  ScrollToTop,
} from "@/components/scroll-to-top";
import { Providers } from "./providers/providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Cheremushki",
  description: "Local russian community",
  openGraph: {
    title: "Cheremushki",
    description: "Local russian community",
    url: "https://cheremushki.vercel.app",
    siteName: "Cheremushki",
    images: [
      {
        url: "https://cheremushki.vercel.app/social-preview.png",
        width: 1200,
        height: 630,
        alt: "Cheremushki preview",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Cheremushki",
    description: "Local russian community",
    images: ["https://Cheremushki.vercel.app/social-preview.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased h-screen overflow-hidden flex flex-col bg-bg`}
      >
        <Providers>
          <Header />
          <ScrollToTop />
          <main
            id={APP_SCROLL_CONTAINER_ID}
            className="flex-1 min-h-0 overflow-auto pt-14 pb-16 sm:pt-16 sm:pb-20"
          >
            <div className="mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-8">
              {children}
            </div>
          </main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
