"use client";

import { LoginModal } from "@/components/LoginModal";
import { useApp } from "@/providers/AppProvider";
import { LogIn } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
export default function Home() {
  const { openLogin, isLoggedIn, showLogin, closeLogin, login, signUp } =
    useApp();

  return (
    <>
      <div className="text-foreground font-sans flex items-center justify-center px-4 min-h-[75vh]">
        <div className="max-w-5xl flex flex-col-reverse md:flex-row items-center md:items-center justify-between gap-10">
          <div className="flex flex-col items-center md:items-start text-center md:text-left gap-6">
            <h2 className="text-4xl md:text-5xl font-semibold">
              Клуб Черемушки
            </h2>
            <p className="text-lg md:text-xl text-darkest">
              Профессиональное сообщество на Севере Германии
            </p>
            <button
              type="button"
              onClick={() => openLogin()}
              className="button-gray-rounded"
            >
              Войти
              <LogIn />
            </button>
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

          {showLogin && (
            <LoginModal
              onClose={closeLogin}
              onLogin={login}
              onRegister={signUp}
            />
          )}
        </div>
      </div>
      
      <section className="section-block text-foreground font-sans">
        <p className="section-block__text flex justify-center font-black">
          Не знаешь, зачем всё это и с чего начать?
        </p>

        <p className="section-block__text flex justify-center">
          Пролистай ниже — мы коротко объясним, как устроен клуб и чем он может
          быть полезен.
        </p>
      </section>
      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">Зачем нужен клуб</h2>

        <p className="section-block__text">
          Ты с рождения живёшь в Германии или только недавно сюда приехал? В
          любом случае иногда не хватает людей, с которыми не нужно долго
          объяснять свой культурный контекст, шутки и жизненный опыт.
        </p>

        <p className="section-block__text">
          «Черёмушки» — закрытое сообщество русскоязычных специалистов из
          Бремена и соседних городов. Мы хотим создать место, где можно
          знакомиться, обмениваться опытом, находить профессиональные контакты,
          просить совета и просто проводить время с интересными людьми.
        </p>

        <p className="section-block__text">
          Это не очередной бесконечный чат и не площадка для сбора подписчиков.
          Главная ценность клуба — люди и отношения между ними.
        </p>
      </section>
      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">
          Кто здесь собирается
        </h2>

        <p className="section-block__text">
          В клубе встречаются специалисты из разных профессий и с разным
          жизненным опытом. Неважно, работаешь ты в IT, медицине, образовании,
          промышленности, творческой сфере или развиваешь собственное дело.
        </p>

        <p className="section-block__text">
          Нам важнее, чтобы участники были открыты к знакомству, уважали других
          и были готовы не только получать пользу от сообщества, но и делиться
          своим опытом.
        </p>
      </section>
      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">Как всё устроено</h2>

        <p className="section-block__text">
          Сайт — это вход в клуб и место, где собрана основная информация.
          Общение участников происходит в закрытой Telegram-группе.
        </p>

        <p className="section-block__text">
          Чтобы вступить, нужно заполнить небольшую анкету и рассказать о себе.
          Мы рассматриваем каждую заявку вручную: это помогает сохранить
          доверительную атмосферу и не превращать клуб в случайный открытый чат.
        </p>

        <p className="section-block__text">
          После одобрения ты получишь персональную ссылку для вступления в
          Telegram-группу.
        </p>
      </section>
      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">
          Что происходит внутри
        </h2>

        <p className="section-block__text">
          В Telegram-группе есть отдельные темы для знакомств, работы и карьеры,
          профессиональных вопросов, жизни в Германии, событий, досуга и
          барахолки.
        </p>

        <p className="section-block__text">
          Можно задать вопрос, попросить рекомендацию, рассказать о своём опыте,
          найти специалиста, предложить встречу или просто поддержать разговор.
          Не нужно ждать особого повода и не обязательно быть самым активным
          участником. Пользуйся клубом в удобном для себя ритме.
        </p>

        <p className="section-block__text">
          Если не знаешь, куда написать, начинай с общей темы.
        </p>
      </section>
      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">Взаимная помощь</h2>

        <p className="section-block__text">
          Клуб придерживается принципа взаимности. Если тебе помогли советом,
          контактом или делом, постарайся со временем предложить что-то другим.
        </p>

        <p className="section-block__text">
          Это не означает, что за каждую помощь нужно немедленно отвечать
          услугой. Достаточно не относиться к сообществу как к бесплатному
          сервису и помнить, что оно существует благодаря вкладу участников.
        </p>

        <p className="section-block__text">
          Полезным может оказаться не только профессиональный контакт. Иногда
          достаточно поделиться личным опытом, ответить на вопрос новичка или
          составить кому-то хорошую компанию.
        </p>
      </section>
      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">Уважение и доверие</h2>

        <p className="section-block__text">
          За каждым сообщением стоит живой человек. В клубе можно спорить и
          иметь разные взгляды, но нельзя переходить на личности, унижать других
          или намеренно провоцировать конфликт.
        </p>

        <p className="section-block__text">
          Закрытость клуба помогает говорить свободнее, но не означает
          вседозволенность. Не выноси чужие сообщения, фотографии и личные
          данные за пределы сообщества без разрешения автора.
        </p>

        <p className="section-block__text">
          Реклама, массовые рассылки и навязчивое продвижение здесь не нужны.
          Рассказывать о своей работе, проектах и услугах можно открыто и по
          делу — особенно если это действительно полезно другим.
        </p>
      </section>
      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">Модерация</h2>

        <p className="section-block__text">
          Модерация нужна не для контроля каждого слова, а для сохранения
          спокойной и доброжелательной атмосферы.
        </p>

        <p className="section-block__text">
          Мы не хотим создавать сложную систему запретов. Большинство ситуаций
          решается обычным уважением к собеседникам и здравым смыслом. Если
          общение становится агрессивным, нарушает приватность участников или
          мешает жизни сообщества, администраторы могут вмешаться.
        </p>
      </section>
      <section className="section-block text-foreground font-sans">
        <h2 className="section-block__title font-black">Начнём?</h2>

        <p className="section-block__text">
          Если тебе близка идея клуба, заполни анкету и немного расскажи о себе.
          После рассмотрения заявки мы свяжемся с тобой по указанным контактам.
        </p>
      </section>
      
    </>
  );
}
