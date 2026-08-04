"use client";

export default function RulesPage() {
  return (
    <main className="mx-auto w-full max-w-3xl py-4">
      <header className="mx-auto mb-10 max-w-3xl text-center">
        <h1 className="mt-3 text-4xl font-black tracking-tight">
          Правила и условия участия
        </h1>

        <p className="section-block__text">
          Эти правила помогают сохранить «Черёмушки» местом, где люди <em>доверяют
          друг другу</em>, <em>свободно общаются</em> и <em>не боятся просить помощи</em>.
        </p>

        <p className="section-block__text">
          Вступая в клуб, участник подтверждает, что ознакомился с правилами и
          согласен их соблюдать.
        </p>
      </header>

      <section className="section-block">
        <h2 className="section-block__title font-black">1. Общение</h2>

        <p className="section-block__text">
          В клубе можно спорить, не соглашаться и обсуждать сложные темы. При
          этом необходимо <em>уважать собеседников</em> и <em>отделять критику идеи от оценки
          человека</em>.
        </p>

        <p className="section-block__text">В клубе недопустимы:</p>

        <ul className="section-block__list list-disc">
          <li className="section-block__list-item">
            оскорбления и переходы на личности;
          </li>

          <li className="section-block__list-item">
            травля, угрозы и дискриминация;
          </li>

          <li className="section-block__list-item">
            намеренное провоцирование конфликтов;
          </li>

          <li className="section-block__list-item">
            спам и массовые рассылки;
          </li>

          <li className="section-block__list-item">навязчивая реклама;</li>

          <li className="section-block__list-item">
            незаконные предложения и материалы.
          </li>
        </ul>

        <p className="section-block__text">
          Политические события можно обсуждать, если они непосредственно связаны
          с жизнью и работой в Германии. Агитация и бесконечные политические
          споры не являются целью клуба.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          2. Взаимная помощь и самопрезентация
        </h2>

        <p className="section-block__text">
          В клубе можно просить совета, рекомендации, контакты и поддержку. По
          возможности <em>делитесь собственным опытом</em> и <em>помогайте другим</em>.
        </p>

        <p className="section-block__text">
          Рассказывать о своей работе, проектах и услугах можно открыто и по
          делу. Если у вас есть <em>личная или коммерческая заинтересованность</em> в
          рекомендации, сообщите об этом.
        </p>

        <p className="section-block__text">
          Использовать клуб только как площадку для рекламы, массового поиска
          клиентов или рассылки одинаковых предложений запрещено.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">3. Приватность</h2>

        <p className="section-block__text">
          Не публикуйте за пределами клуба чужие сообщения, фотографии, контактные
          данные и другую личную информацию без разрешения автора.
        </p>

        <p className="section-block__text">
          Если хотите переслать сообщение или познакомить участника с человеком
          вне клуба, сначала спросите его <em>согласие</em>.
        </p>

        <p className="section-block__text">
          Закрытость сообщества не гарантирует абсолютную конфиденциальность. Не
          публикуйте документы, пароли, финансовые данные и другую информацию,
          распространение которой может причинить вред.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">4. Вступление</h2>

        <p className="section-block__text">
          Для вступления необходимо пройти процедуру регистрации, активировать
          аккаунт по ссылке из письма, а затем заполнить анкету, предоставив{" "}
          <em>достоверную информацию о себе</em>.
        </p>

        <p className="section-block__text">
          После активации аккаунта участник получает доступ на страницу клуба и
          персональную ссылку на закрытую Telegram-группу. Данную ссылку нельзя
          публиковать или передавать другим людям. После вступления в группу
          профиль публикуется в разделе «Наши люди».
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          5. Ответственность участников
        </h2>

        <p className="section-block__text">
          Участники самостоятельно оценивают советы, рекомендации, вакансии,
          товары и услуги, о которых узнают в клубе.
        </p>

        <p className="section-block__text">
          Личный опыт участников не заменяет медицинскую, юридическую, налоговую
          или финансовую консультацию.
        </p>

        <p className="section-block__text">
          Договорённости между участниками заключаются на их <em>собственную
          ответственность</em>. Администрация клуба не является стороной таких
          договорённостей.
        </p>

        <p className="section-block__text">
          Работа Telegram регулируется условиями самого сервиса. Клуб не
          управляет его инфраструктурой и не может гарантировать его постоянную
          доступность.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">6. Модерация</h2>

        <p className="section-block__text">
          Модерация нужна для сохранения <em>спокойной и доброжелательной атмосферы</em>,
          а не для определения единственно правильного мнения.
        </p>

        <p className="section-block__text">Модераторы могут:</p>

        <ul className="section-block__list list-disc">
          <li className="section-block__list-item">
            обратить внимание участника на неподходящее поведение;
          </li>

          <li className="section-block__list-item">
            попросить завершить или перенести обсуждение;
          </li>

          <li className="section-block__list-item">
            удалить сообщение, нарушающее правила;
          </li>

          <li className="section-block__list-item">
            временно ограничить возможность общения;
          </li>

          <li className="section-block__list-item">
            исключить участника из клуба.
          </li>
        </ul>

        <p className="section-block__text">
          Обычно мы сначала стараемся <em>обсудить проблему</em>. При угрозах, травле,
          публикации чужих персональных данных или намеренном причинении вреда
          участник может быть исключён без предварительного предупреждения.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          7. Прекращение участия
        </h2>

        <p className="section-block__text">
          Участник может в любой момент <em>покинуть клуб</em>.
        </p>

        <p className="section-block__text">
          Если человек систематически нарушает правила или его поведение мешает
          другим участникам, администрация может прекратить его участие.
        </p>

        <p className="section-block__text">
          Для удаления данных, переданных через сайт, необходимо написать по
          адресу{" "}
          <a href="mailto:[EMAIL]" className="underline">
            [EMAIL]
          </a>
          .
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">8. Изменение правил</h2>

        <p className="section-block__text">
          Правила могут уточняться по мере развития клуба. Актуальная редакция
          всегда публикуется на этой странице.
        </p>

        <p className="section-block__text">
          О <em>существенных изменениях</em> мы сообщим участникам в Telegram-группе.
        </p>

        <p className="section-block__text">Последнее обновление: [ДАТА]</p>
      </section>
    </main>
  );
}
