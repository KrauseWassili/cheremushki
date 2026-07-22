"use client";

export default function RulesPage() {
  return (
    <div className="max-w-5xl min-h-screen flex flex-col items-start px-4 text-left">
      <section className="section-block">
        <h1 className="section-block__title font-black">
          Правила и условия участия
        </h1>

        <p className="section-block__text">
          Эти правила помогают сохранить «Черёмушки» местом, где люди доверяют
          друг другу, свободно общаются и не боятся просить помощи.
        </p>

        <p className="section-block__text">
          Вступая в клуб, участник подтверждает, что ознакомился с правилами и
          согласен их соблюдать.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">1. Общение</h2>

        <p className="section-block__text">
          В клубе можно спорить, не соглашаться и обсуждать сложные темы. При
          этом необходимо уважать собеседников и отделять критику идеи от оценки
          человека.
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
          возможности делись собственным опытом и помогай другим.
        </p>

        <p className="section-block__text">
          Рассказывать о своей работе, проектах и услугах можно открыто и по
          делу. Если у тебя есть личная или коммерческая заинтересованность в
          рекомендации, сообщи об этом.
        </p>

        <p className="section-block__text">
          Использовать клуб только как площадку для рекламы, массового поиска
          клиентов или рассылки одинаковых предложений нельзя.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">3. Приватность</h2>

        <p className="section-block__text">
          Не публикуй за пределами клуба чужие сообщения, фотографии, контактные
          данные и другую личную информацию без разрешения автора.
        </p>

        <p className="section-block__text">
          Если хочешь переслать сообщение или познакомить участника с человеком
          вне клуба, сначала спроси его согласие.
        </p>

        <p className="section-block__text">
          Закрытость сообщества не гарантирует абсолютную конфиденциальность. Не
          публикуй документы, пароли, финансовые данные и другую информацию,
          распространение которой может причинить вред.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">4. Вступление</h2>

        <p className="section-block__text">
          Для вступления необходимо заполнить анкету и предоставить достоверную
          информацию о себе.
        </p>

        <p className="section-block__text">
          Все заявки рассматриваются вручную. Отправка анкеты не гарантирует
          вступление. Администрация может одобрить или отклонить заявку.
        </p>

        <p className="section-block__text">
          После одобрения участник получает персональную ссылку на закрытую
          Telegram-группу. Эту ссылку нельзя публиковать или передавать другим
          людям.
        </p>

        <p className="section-block__text">
          Если ты хочешь пригласить знакомого, отправь ему ссылку на анкету.
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
          Договорённости между участниками заключаются на их собственную
          ответственность. Администрация клуба не является стороной таких
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
          Модерация нужна для сохранения спокойной и доброжелательной атмосферы,
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
          Обычно мы сначала стараемся обсудить проблему. При угрозах, травле,
          публикации чужих персональных данных или намеренном причинении вреда
          участник может быть исключён без предварительного предупреждения.
        </p>

        <p className="section-block__text">
          Если ты не согласен с решением модератора, обсуди его с администрацией
          в личной переписке.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          7. Прекращение участия
        </h2>

        <p className="section-block__text">
          Участник может в любой момент покинуть клуб.
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
          О существенных изменениях мы сообщим участникам в Telegram-группе.
        </p>

        <p className="section-block__text">Последнее обновление: [ДАТА]</p>
      </section>
    </div>
  );
}
