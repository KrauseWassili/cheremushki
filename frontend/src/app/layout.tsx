import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Cheremushki',
  description: 'Next.js project generated in Cheremushki workspace',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
