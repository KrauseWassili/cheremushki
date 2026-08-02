import type { Metadata } from "next";
import "@fontsource-variable/golos-text/wght.css";
import "./globals.css";
import Header from "@/components/header";
import Footer from "@/components/footer";
import {
  APP_SCROLL_CONTAINER_ID,
  ScrollToTop,
} from "@/components/scroll-to-top";
import { Providers } from "./providers/providers";

const siteUrl = new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: siteUrl,
  title: "Черемушки",
  description: "Локальное русскоязычное сообщество в Бремене и рядом",
  openGraph: {
    title: "Черемушки",
    description: "Локальное русскоязычное сообщество в Бремене и рядом",
    url: siteUrl?.toString(),
    siteName: "Черемушки",
    images: [
      {
        url: "/social-preview.png",
        width: 1200,
        height: 630,
        alt: "Превью клуба Черемушки",
      },
    ],
    locale: "ru_RU",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Черемушки",
    description: "Локальное русскоязычное сообщество в Бремене и рядом",
    images: ["/social-preview.png"],
  },
};
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <body
        className="flex h-screen flex-col overflow-hidden bg-bg antialiased"
      >
        <Providers>
          <Header />
          <ScrollToTop />
          <main
            id={APP_SCROLL_CONTAINER_ID}
            className="flex-1 min-h-0 overflow-auto pt-14 pb-32 min-[900px]:pb-20"
          >
            <div className="mx-auto w-full max-w-3xl px-4">
              {children}
            </div>
          </main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
