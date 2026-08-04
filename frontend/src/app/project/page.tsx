"use client";

export default function AboutPage() {
  return (
    <main className="mx-auto w-full max-w-3xl py-4">
      <header className="text-page-header mx-auto mb-10 max-w-3xl text-center">
        <h1 className="mt-3 text-4xl font-bold tracking-tight">
          О проекте
        </h1>

        <p className="section-block__text">
          «Черёмушки» — <em>частная инициатива</em> по созданию <em>закрытого сообщества</em>
            русскоязычных специалистов из Бремена и соседних городов.
        </p>

        <p className="section-block__text">
          Проект появился из <em>простой идеи</em>: рядом живёт много интересных людей,
            но у них почти нет <em>общего пространства</em>, в котором можно
            познакомиться, обменяться опытом и продолжить общение за пределами
            случайной встречи.
        </p>
      </header>

      <section className="section-block">
        <h2 className="section-block__title font-bold">
          Почему локальное сообщество
        </h2>

        <p className="section-block__text">
          В интернете уже достаточно больших русскоязычных чатов и сообществ. Но
          чем шире их аудитория, тем сложнее превратить знакомство в <em>реальные
          отношения</em>.
        </p>

        <p className="section-block__text">
          «Черёмушки» сосредоточены на Бремене и городах вокруг него. Это
          позволяет не только переписываться, но и <em>встречаться</em>, знакомить людей
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
        <h2 className="section-block__title font-bold">
          Почему клуб закрытый
        </h2>

        <p className="section-block__text">
          Закрытость нужна <em>не для создания ощущения избранности</em>. Она помогает
          участникам понимать, с кем они общаются, и <em>свободнее делиться личным</em>
          опытом.
        </p>

        <p className="section-block__text">
          Поэтому после вступления мы просим вас заполнить анкету.
        </p>

        <p className="section-block__text">
          Мы не стремимся принять как можно больше людей. Нам важнее собрать
          сообщество, в котором участники <em>доверяют друг другу</em> и чувствуют себя
          комфортно.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-bold">
          Кто занимается проектом
        </h2>

        <p className="section-block__text">
          На первом этапе «Черёмушки» развиваются как частная инициатива. За
          сайтом и организацией сообщества стоит частный организатор, а не
          компания или коммерческая платформа.
        </p>

        <p className="section-block__text">
          Юридическая информация об ответственном за сайт приведена в разделе{" "}
          <a href="/legal" className="underline">
            правовой информации
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
        <h2 className="section-block__title font-bold">
          Деньги и независимость
        </h2>

        <p className="section-block__text">
          На первом этапе <em>участие в клубе бесплатно</em>. У проекта нет платной
          подписки, рекламы, инвесторов и скрытых коммерческих интеграций.
        </p>

        <p className="section-block__text">
          Если модель клуба изменится, участники заранее получат <em>понятную
          информацию о новых условиях</em>.
        </p>

        <p className="section-block__text">
          Рекомендации внутри сообщества могут касаться компаний, услуг и
          проектов участников. В таких случаях мы просим открыто сообщать о
          личной или коммерческой заинтересованности.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-bold">
          Как развивается проект
        </h2>

        <p className="section-block__text">
          Мы начинаем с простой модели: сайт, анкета и закрытая Telegram-группа.
        </p>

        <p className="section-block__text">
          Сейчас нам не нужны сложная социальная сеть, рейтинги, алгоритмические
          ленты или внутренний мессенджер. Telegram уже хорошо решает задачу
          <em>живого общения</em>.
        </p>

        <p className="section-block__text">
          Новые возможности будут появляться только тогда, когда станут
          <em>действительно нужны участникам</em>. Мы хотим развивать клуб постепенно и
          не усложнять его ради самого усложнения.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-bold">
          Участие и инициативы
        </h2>

        <p className="section-block__text">
          Клуб не строится только вокруг одного организатора. Участники
          могут предлагать встречи, создавать совместные проекты, делиться
          профессиональным опытом и запускать <em>собственные инициативы</em>.
        </p>

        <p className="section-block__text">
          Не обязательно ждать разрешения на каждую идею. Если она не нарушает
          правила и может быть полезна сообществу, её можно предложить другим
          участникам.
        </p>
      </section>

      <section id="contact" className="section-block">
        <h2 className="section-block__title font-bold">Связаться с нами</h2>

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
