import Link from "next/link";
import { JoinDemoProvider } from "@/components/join/join-demo-provider";
import { JoinStepper } from "@/components/join/join-stepper";

type JoinLayoutProps = {
  children: React.ReactNode;
};

export default function JoinLayout({
  children,
}: JoinLayoutProps) {
  return (
    <JoinDemoProvider>
      <main className="min-h-screen bg-muted/30 px-4 py-8 sm:py-14">
        <div className="mx-auto w-full max-w-3xl">
          <div className="mb-7 text-center">
            <Link
              href="/"
              className="text-2xl font-black tracking-tight"
            >
              Черёмушки
            </Link>

            <p className="mt-1 text-sm text-muted-foreground">
              Вступление в сообщество
            </p>
          </div>

          <div className="rounded-3xl border border-border bg-background p-6 shadow-sm sm:p-10">
            <JoinStepper />

            {children}
          </div>

          <p className="mt-6 text-center text-xs text-muted-foreground">
            Это демонстрационная версия. Письма и данные
            никуда не отправляются.
          </p>
        </div>
      </main>
    </JoinDemoProvider>
  );
}