"use client";

import { useApp } from "@/providers/AppProvider";
import Image from "next/image";

export default function Home() {
  const { openLogin } = useApp();

  return (
    <>
      <div className="home-first-screen">
        <section className="section-block home-hero-section text-foreground font-sans">
          <div className="flex items-center">
            <div className="w-full">
              <div className="max-w-3xl w-full mx-auto flex flex-col-reverse min-[900px]:flex-row items-center justify-between gap-10">
                <div className="flex flex-col items-center min-[900px]:items-start text-center min-[900px]:text-left gap-6 min-[900px]:w-1/2">
                  <h1 className="text-4xl font-semibold text-ink min-[900px]:text-5xl">
                    Клуб Черемушки
                  </h1>
                  <p className="text-lg text-primary min-[900px]:text-xl">
                    <em>
                      Закрытое сообщество русскоязычных специалистов из Бремена и
                      соседних городов.
                    </em>
                  </p>
                </div>

                <div className="flex justify-center min-[900px]:justify-end w-full min-[900px]:w-1/2">
                  <Image
                    src="/hero_banner.webp"
                    alt=""
                    width={300}
                    height={300}
                    className="w-64 h-auto rounded-xl shadow-[0_14px_36px_color-mix(in_srgb,var(--palette-ink)_20%,transparent)]"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>
        <section className="section-block home-intro-teaser text-foreground font-sans">
          <p className="section-block__text flex justify-center font-black text-primary">
            Не знаете, зачем всё это и с чего начать?
          </p>

          <p className="section-block__text text-center">
            Ниже коротко объясняем, как устроен клуб и чем он полезен.
          </p>
          <p className="section-block__text text-center">
            Подробнее можно узнать{" "}
            <a href="/project" className="underline">
              о проекте
            </a>{" "}
            или прочитать{" "}
            <a href="/rules" className="underline">
              правила клуба
            </a>
            .
          </p>
        </section>
      </div>
      <section id="about" className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">Зачем нужен клуб</h2>

        <p className="section-block__text">
          Вы с рождения живёте в Германии или только недавно сюда приехали? В
          любом случае иногда <em>не хватает людей</em>, с которыми не нужно долго
          объяснять свой культурный контекст, шутки и жизненный опыт.
        </p>

        <p className="section-block__text">
          Мы хотим создать <em>место, где такие люди смогут находить друг друга</em>,
          знакомиться и выстраивать долгосрочные отношения.
        </p>

        <p className="section-block__text">
          Это <em>не очередной бесконечный чат</em> и не площадка для сбора подписчиков.
          <em>Главная ценность клуба</em> — люди и отношения между ними.
        </p>
      </section>

      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">
          Что происходит внутри
        </h2>

        <p className="section-block__text">
          Общение проходит в <em>закрытой Telegram-группе</em>. В ней есть отдельные темы
          для знакомств, работы и карьеры, профессиональных вопросов, жизни в
          Германии, событий, досуга и барахолки.
        </p>

        <p className="section-block__text">
          Можно задать вопрос, попросить рекомендацию, рассказать о своём опыте,
          найти специалиста, предложить встречу или просто поддержать разговор.
        </p>

        <p className="section-block__text">
          Не обязательно писать каждый день или участвовать во всех обсуждениях.
          Пользуйтесь клубом <em>в комфортном для себя ритме</em>.
        </p>
      </section>

      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">Как всё устроено</h2>

        <ol className="ml-5 list-decimal space-y-3 text-lg leading-8 text-body marker:text-accent">
          <li>Пройдите процедуру регистрации.</li>

          <li>Расскажите подробнее о себе, заполнив небольшую анкету.</li>

          <li>
            После регистрации вы получите доступ в клуб и пригласительную ссылку
            для вступления в закрытую Telegram-группу.
          </li>
        </ol>
      </section>

      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">
          На чём держится сообщество
        </h2>

        <h3 className="section-block__subtitle font-bold">Взаимная помощь</h3>

        <p className="section-block__text">
          Здесь можно <em>просить помощи</em>. Взамен мы предлагаем участникам по
          возможности <em>делиться собственным опытом</em> и помогать другим.
        </p>

        <h3 className="section-block__subtitle font-bold">Уважение</h3>

        <p className="section-block__text">
          Можно спорить и иметь разные взгляды, но <em>нельзя унижать собеседника</em>,
          переходить на личности или намеренно провоцировать конфликт.
        </p>

        <h3 className="section-block__subtitle font-bold">Доверие</h3>

        <p className="section-block__text">
          Мы общаемся как <em>реальные люди</em> и бережно относимся к информации,
          которой делятся участники.
        </p>

        <p className="section-block__text">
          Подробности приведены в{" "}
          <a href="/rules" className="underline">
            правилах клуба
          </a>
          .
        </p>
      </section>

      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">
          Хотите присоединиться?
        </h2>

        <p className="section-block__text">
          Если вам близка идея клуба, прочитайте правила и {" "}
          <button
            type="button"
            onClick={() => openLogin("register")}
            className="button-flat cursor-pointer p-0 font-bold text-link underline underline-offset-[0.18em] transition-colors hover:text-link-hover"
          >
            зарегистрируйтесь.
          </button>
        </p>
      </section>
    </>
  );
}
