"use client";

export default function AboutPage() {
  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-4 sm:px-6 sm:py-6">
      <header className="mx-auto mb-10 max-w-3xl text-center">
        <h1 className="mt-3 text-4xl font-black tracking-tight sm:text-5xl">
          О проекте
        </h1>

        <p className="section-block__text">
          <em>
            «Черёмушки» — частная инициатива по созданию закрытого сообщества
            русскоязычных специалистов из Бремена и соседних городов.
          </em>
        </p>

        <p className="section-block__text">
          <em>
            Проект появился из простой идеи: рядом живёт много интересных людей,
            но у них почти нет общего пространства, в котором можно
            познакомиться, обменяться опытом и продолжить общение за пределами
            случайной встречи.
          </em>
        </p>
      </header>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          Почему локальное сообщество
        </h2>

        <p className="section-block__text">
          В интернете уже достаточно больших русскоязычных чатов и сообществ. Но
          чем шире их аудитория, тем сложнее превратить знакомство в реальные
          отношения.
        </p>

        <p className="section-block__text">
          «Черёмушки» сосредоточены на Бремене и городах вокруг него. Это
          позволяет не только переписываться, но и встречаться, знакомить людей
          друг с другом, посещать мероприятия и создавать собственные
          инициативы.
        </p>

        <p className="section-block__text">
          При этом клуб не посвящён одному городу как теме. Внутри можно
          говорить о работе, профессии, жизни в Германии, путешествиях,
          увлечениях и обо всём, что интересно участникам.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          Почему клуб закрытый
        </h2>

        <p className="section-block__text">
          Закрытость нужна не для создания ощущения избранности. Она помогает
          участникам понимать, с кем они общаются, и свободнее делиться личным
          опытом.
        </p>

        <p className="section-block__text">
          Поэтому после вступления мы просим вас заполнить анкету.
        </p>

        <p className="section-block__text">
          Мы не стремимся принять как можно больше людей. Нам важнее собрать
          сообщество, в котором участники доверяют друг другу и чувствуют себя
          комфортно.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          Кто занимается проектом
        </h2>

        <p className="section-block__text">
          На первом этапе «Черёмушки» развиваются как частная инициатива. За
          сайтом и организацией сообщества стоит частный организатор, а не
          компания или коммерческая платформа.
        </p>

        <p className="section-block__text">
          Юридическая информация об ответственном за сайт приведена в{" "}
          <a href="/impressum" className="underline">
            Impressum
          </a>
          .
        </p>

        <p className="section-block__text">
          Информация об обработке анкет и других персональных данных приведена в{" "}
          <a href="/privacy" className="underline">
            политике конфиденциальности
          </a>
          .
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          Деньги и независимость
        </h2>

        <p className="section-block__text">
          На первом этапе участие в клубе бесплатно. У проекта нет платной
          подписки, рекламы, инвесторов и скрытых коммерческих интеграций.
        </p>

        <p className="section-block__text">
          Если модель клуба изменится, участники заранее получат понятную
          информацию о новых условиях.
        </p>

        <p className="section-block__text">
          Рекомендации внутри сообщества могут касаться компаний, услуг и
          проектов участников. В таких случаях мы просим открыто сообщать о
          личной или коммерческой заинтересованности.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          Как развивается проект
        </h2>

        <p className="section-block__text">
          Мы начинаем с простой модели: сайт, анкета и закрытая Telegram-группа.
        </p>

        <p className="section-block__text">
          Сейчас нам не нужны сложная социальная сеть, рейтинги, алгоритмические
          ленты или внутренний мессенджер. Telegram уже хорошо решает задачу
          живого общения.
        </p>

        <p className="section-block__text">
          Новые возможности будут появляться только тогда, когда станут
          действительно нужны участникам. Мы хотим развивать клуб постепенно и
          не усложнять его ради самого усложнения.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          Участие и инициативы
        </h2>

        <p className="section-block__text">
          Клуб не строится только вокруг одного организатора. Участники
          могут предлагать встречи, создавать совместные проекты, делиться
          профессиональным опытом и запускать собственные инициативы.
        </p>

        <p className="section-block__text">
          Не обязательно ждать разрешения на каждую идею. Если она не нарушает
          правила и может быть полезна сообществу, её можно предложить другим
          участникам.
        </p>
      </section>

      <section id="contact" className="section-block">
        <h2 className="section-block__title font-black">Связаться с нами</h2>

        <p className="section-block__text">
          Если у вас есть вопрос о клубе, заявке, правилах или обработке
          персональных данных, напиши на электронную почту:
        </p>

        <p className="section-block__text">
          <a href="mailto:[EMAIL]" className="underline">
            [EMAIL]
          </a>
        </p>

        <p className="section-block__text">
          Если вопрос связан с уже поданной заявкой, укажите в письме имя и адрес
          электронной почты, которые использовали при заполнении анкеты.
        </p>
      </section>
    </main>
  );
}
