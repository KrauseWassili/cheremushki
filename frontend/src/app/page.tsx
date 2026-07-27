"use client";

import { useApp } from "@/providers/AppProvider";
import Image from "next/image";

export default function Home() {
  const { openLogin } = useApp();

  return (
    <>
      <section className="section-block text-foreground font-sans">
        <div className="min-h-[70vh] flex items-center px-4">
          <div className="w-full">
            <div className="max-w-5xl w-full mx-auto flex flex-col-reverse md:flex-row items-center justify-between gap-10">
              <div className="flex flex-col items-center md:items-start text-center md:text-left gap-6 md:w-1/2">
                <h1 className="text-4xl md:text-5xl font-semibold">
                  Клуб Черемушки
                </h1>
                <p className="text-lg md:text-xl text-darkest">
                  <em>
                    Закрытое сообщество русскоязычных специалистов из Бремена и
                    соседних городов.
                  </em>
                </p>
              </div>

              <div className="flex justify-center md:justify-end w-full md:w-1/2">
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
        </div>
      </section>
      <section className="section-block text-foreground font-sans">
        <p className="section-block__text flex justify-center font-black">
          Не знаете, зачем всё это и с чего начать?
        </p>

        <p className="section-block__text text-center">
          Пролистайте ниже — мы коротко объясним, как устроен клуб и чем он
          может быть полезен.
        </p>
        <p className="section-block__text text-center">
          Можете также подробнее узнать{" "}
          <a href="/project" className="underline">
            о нашем проекте
          </a>{" "}
          или прочитать{" "}
          <a href="/rules" className="underline">
            правила клуба
          </a>
          .
        </p>
      </section>
      <section id="about" className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">Зачем нужен клуб</h2>

        <p className="section-block__text">
          Вы с рождения живёте в Германии или только недавно сюда приехали? В
          любом случае иногда не хватает людей, с которыми не нужно долго
          объяснять свой культурный контекст, шутки и жизненный опыт.
        </p>

        <p className="section-block__text">
          Мы хотим создать место, где такие люди смогут находить друг друга,
          знакомиться и выстраивать долгосрочные отношения.
        </p>

        <p className="section-block__text">
          Это не очередной бесконечный чат и не площадка для сбора подписчиков.
          Главная ценность клуба — люди и отношения между ними.
        </p>
      </section>

      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">
          Что происходит внутри
        </h2>

        <p className="section-block__text">
          Общение проходит в закрытой Telegram-группе. В ней есть отдельные темы
          для знакомств, работы и карьеры, профессиональных вопросов, жизни в
          Германии, событий, досуга и барахолки.
        </p>

        <p className="section-block__text">
          Можно задать вопрос, попросить рекомендацию, рассказать о своём опыте,
          найти специалиста, предложить встречу или просто поддержать разговор.
        </p>

        <p className="section-block__text">
          Не обязательно писать каждый день или участвовать во всех обсуждениях.
          Пользуйтесь клубом в комфортном для себя ритме.
        </p>
      </section>

      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">Как всё устроено</h2>

        <ol className="ml-5 list-decimal space-y-3 text-lg leading-8 text-darkest sm:ml-5">
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
          Здесь можно просить помощи. Взамен мы предлагаем участникам по
          возможности делиться собственным опытом и помогать другим.
        </p>

        <h3 className="section-block__subtitle font-bold">Уважение</h3>

        <p className="section-block__text">
          Можно спорить и иметь разные взгляды, но нельзя унижать собеседника,
          переходить на личности или намеренно провоцировать конфликт.
        </p>

        <h3 className="section-block__subtitle font-bold">Доверие</h3>

        <p className="section-block__text">
          Мы общаемся как реальные люди и бережно относимся к информации,
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
          Если вам близка идея клуба, прочитайте правила и
          <button
            type="button"
            onClick={() => openLogin("register")}
            className="underline cursor-pointer rounded-md px-2 py-2 font-medium text-secondary transition-colors hover:bg-white/10 hover:text-foreground"
          >
            зарегистрируйтесь.
          </button>
        </p>
      </section>
    </>
  );
}
