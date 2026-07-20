import Buttons from "@/components/buttons-home-page";
import Image from "next/image";
export default function Home() {
  return (
    <div className="text-foreground font-sans flex items-center justify-center px-4 min-h-[90vh]">
      <div className="w-full max-w-5xl flex flex-col-reverse md:flex-row items-center md:items-center justify-between gap-10">
        <div className="flex flex-col items-center md:items-start text-center md:text-left gap-6">
          <h2 className="text-4xl md:text-5xl font-semibold">
            Клуб Черемушки
          </h2>
          <p className="text-lg md:text-xl text-darkest">
            Профессиональное сообщество Севера Германии
          </p>
          <Buttons />
        </div>

        <div className="flex justify-center md:justify-end w-full md:w-auto">
          <Image
            src="/hero_banner.png"
            alt=""
            width={300}
            height={300}
            className="w-64 h-auto rounded-xl shadow-lg"
          />
        </div>
      </div>
    </div>
  );
}
