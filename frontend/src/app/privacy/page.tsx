"use client";

import { useApp } from "@/providers/AppProvider";
import { LogIn } from "lucide-react";
import Link from "next/link";

export default function PrivacyPage() {
  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-4 sm:px-6 sm:py-6">
      <header className="mx-auto mb-10 max-w-3xl text-center">
        <h1 className="mt-3 text-4xl font-black tracking-tight sm:text-5xl">
          Политика конфиденциальности
        </h1>

        <p className="section-block__text">
          В этой политике мы объясняем, какие персональные данные обрабатывает
          сайт клуба «Черёмушки», зачем они необходимы и какими правами обладает
          пользователь.
        </p>

        <p className="section-block__text">
          Мы собираем только те данные, которые нужны для работы сайта,
          рассмотрения заявок и организации участия в клубе.
        </p>

        <p className="section-block__text">Последнее обновление: 21.07.2026</p>
      </header>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          1. Ответственный за обработку данных
        </h2>

        <address className="section-block__text not-italic">
          [ИМЯ И ФАМИЛИЯ ИЛИ НАЗВАНИЕ ОРГАНИЗАЦИИ]
          <br />
          [УЛИЦА И НОМЕР ДОМА]
          <br />
          [ИНДЕКС И ГОРОД]
          <br />
          Германия
          <br />
          Email:{" "}
          <a href="mailto:[EMAIL]" className="underline">
            [EMAIL]
          </a>
        </address>

        <p className="section-block__text">
          Ответственный определяет цели и способы обработки персональных данных
          в соответствии с Общим регламентом ЕС по защите данных (GDPR/DSGVO).
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          2. Технические данные при посещении сайта
        </h2>

        <p className="section-block__text">
          При открытии сайта хостинг-провайдер может автоматически обрабатывать
          техническую информацию, необходимую для передачи страницы и
          обеспечения безопасности.
        </p>

        <p className="section-block__text">Такая информация может включать:</p>

        <ul className="section-block__list list-disc">
          <li className="section-block__list-item">IP-адрес;</li>
          <li className="section-block__list-item">дату и время обращения;</li>
          <li className="section-block__list-item">
            адрес запрошенной страницы;
          </li>
          <li className="section-block__list-item">
            тип браузера и операционной системы;
          </li>
          <li className="section-block__list-item">
            адрес страницы, с которой был выполнен переход;
          </li>
          <li className="section-block__list-item">
            технические сведения об ошибках и состоянии запроса.
          </li>
        </ul>

        <p className="section-block__text">
          Эти данные используются для предоставления сайта, обеспечения его
          стабильности, обнаружения ошибок и защиты от злоупотреблений.
        </p>

        <p className="section-block__text">
          Правовым основанием является статья 6(1)(f) GDPR — наш законный
          интерес в безопасной и надёжной работе сайта.
        </p>

        <p className="section-block__text">
          Срок хранения технических журналов: [УКАЗАТЬ ФАКТИЧЕСКИЙ СРОК].
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          3. Данные, передаваемые через анкету
        </h2>

        <p className="section-block__text">
          При подаче заявки на вступление мы обрабатываем сведения, которые
          пользователь самостоятельно указывает в анкете.
        </p>

        <p className="section-block__text">
          В зависимости от окончательного содержания формы это могут быть:
        </p>

        <ul className="section-block__list list-disc">
          <li className="section-block__list-item">имя и фамилия;</li>
          <li className="section-block__list-item">адрес электронной почты;</li>
          <li className="section-block__list-item">город проживания;</li>
          <li className="section-block__list-item">
            профессия и место работы;
          </li>
          <li className="section-block__list-item">
            имя пользователя в Telegram;
          </li>
          <li className="section-block__list-item">
            ссылка на профессиональный профиль;
          </li>
          <li className="section-block__list-item">
            информация о профессиональном опыте;
          </li>
          <li className="section-block__list-item">
            ответы о мотивации и возможном вкладе в сообщество.
          </li>
        </ul>

        <p className="section-block__text">
          Данные используются для рассмотрения заявки, связи с кандидатом,
          принятия решения о вступлении и организации доступа в закрытую
          Telegram-группу.
        </p>

        <p className="section-block__text">
          Правовым основанием является статья 6(1)(b) GDPR — обработка данных
          для действий, предпринимаемых по запросу пользователя до начала
          участия в клубе.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          4. Рассмотрение заявки
        </h2>

        <p className="section-block__text">
          Заявки рассматриваются администрацией вручную. В процессе рассмотрения
          заявке присваивается один из статусов: новая, одобренная или
          отклонённая.
        </p>

        <p className="section-block__text">
          Администратор также может добавить внутреннюю заметку, необходимую для
          рассмотрения заявки и фиксации принятого решения.
        </p>

        <p className="section-block__text">
          Решение не принимается исключительно автоматизированными средствами и
          не основывается на автоматическом профилировании.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">5. Сроки хранения</h2>

        <p className="section-block__text">
          Мы храним персональные данные не дольше, чем это необходимо для целей,
          ради которых они были собраны.
        </p>

        <ul className="section-block__list list-disc">
          <li className="section-block__list-item">
            Новые заявки хранятся до завершения рассмотрения.
          </li>

          <li className="section-block__list-item">
            Отклонённые и отозванные заявки удаляются через [ВЫБРАТЬ СРОК,
            НАПРИМЕР 6 МЕСЯЦЕВ].
          </li>

          <li className="section-block__list-item">
            Данные одобренных участников хранятся в течение участия в клубе и
            ещё [ВЫБРАТЬ СРОК] после его прекращения, если более длительное
            хранение не требуется законом.
          </li>

          <li className="section-block__list-item">
            Данные могут быть удалены раньше по обоснованному запросу
            пользователя.
          </li>
        </ul>

        <p className="section-block__text">
          Отдельные сведения могут храниться дольше, если это необходимо для
          выполнения юридической обязанности или защиты от правовых требований.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          6. Поставщики технических услуг
        </h2>

        <p className="section-block__text">
          Для работы сайта мы используем поставщиков технической инфраструктуры,
          которые могут обрабатывать данные по нашему поручению.
        </p>

        <h3 className="section-block__subtitle font-bold">Vercel</h3>

        <p className="section-block__text">
          Сайт размещается на инфраструктуре Vercel. Vercel может обрабатывать
          технические данные запросов, необходимые для доставки страниц,
          обеспечения безопасности и диагностики ошибок.
        </p>

        <p className="section-block__text">Поставщик: Vercel Inc.</p>

        <p className="section-block__text">
          Дополнительная информация:{" "}
          <a
            href="https://vercel.com/legal/privacy-policy"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            политика конфиденциальности Vercel
          </a>
          .
        </p>

        <h3 className="section-block__subtitle font-bold">Supabase</h3>

        <p className="section-block__text">
          Данные заявок хранятся в базе данных Supabase PostgreSQL. Выбранный
          регион размещения проекта: [УКАЗАТЬ РЕГИОН].
        </p>

        <p className="section-block__text">Поставщик: Supabase Inc.</p>

        <p className="section-block__text">
          Дополнительная информация:{" "}
          <a
            href="https://supabase.com/privacy"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            политика конфиденциальности Supabase
          </a>
          .
        </p>

        <p className="section-block__text">
          С поставщиками, обрабатывающими данные по нашему поручению,
          заключаются необходимые соглашения об обработке данных.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">7. Telegram</h2>

        <p className="section-block__text">
          После одобрения заявки участнику может быть направлена ссылка на
          закрытую группу в Telegram.
        </p>

        <p className="section-block__text">
          При переходе в Telegram дальнейшая обработка данных этим сервисом
          осуществляется в соответствии с условиями и политикой
          конфиденциальности Telegram. Клуб не управляет технической
          инфраструктурой Telegram.
        </p>

        <p className="section-block__text">
          Перед вступлением рекомендуем ознакомиться с{" "}
          <a
            href="https://telegram.org/privacy"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            политикой конфиденциальности Telegram
          </a>
          .
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          8. Cookies и аналитика
        </h2>

        <p className="section-block__text">
          На момент публикации сайт не использует рекламные cookies, системы
          отслеживания поведения или стороннюю маркетинговую аналитику.
        </p>

        <p className="section-block__text">
          Если в будущем появятся необязательные cookies или аналитические
          инструменты, эта политика будет обновлена, а при необходимости сайт
          предварительно запросит согласие пользователя.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          9. Передача данных другим лицам
        </h2>

        <p className="section-block__text">
          Мы не продаём персональные данные и не передаём их третьим лицам для
          их собственной рекламы.
        </p>

        <p className="section-block__text">
          Доступ к данным получают только администраторы клуба и поставщики,
          которые необходимы для технической работы сайта.
        </p>

        <p className="section-block__text">
          Передача также может быть выполнена, если этого требует закон или
          обязательное решение уполномоченного органа.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          10. Передача данных за пределы ЕС
        </h2>

        <p className="section-block__text">
          Некоторые поставщики технических услуг могут быть зарегистрированы или
          использовать инфраструктуру за пределами Европейского союза.
        </p>

        <p className="section-block__text">
          В таких случаях передача выполняется только при наличии
          предусмотренного GDPR правового механизма, например решения об
          адекватности или стандартных договорных положений Европейской
          комиссии.
        </p>

        <p className="section-block__text">
          Конкретные механизмы необходимо сверить с действующими договорами
          Vercel и Supabase перед публикацией этой страницы.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          11. Права пользователя
        </h2>

        <p className="section-block__text">
          В предусмотренных GDPR случаях пользователь имеет право:
        </p>

        <ul className="section-block__list list-disc">
          <li className="section-block__list-item">
            получить информацию об обработке своих данных;
          </li>
          <li className="section-block__list-item">
            запросить копию своих данных;
          </li>
          <li className="section-block__list-item">
            исправить неточные или неполные сведения;
          </li>
          <li className="section-block__list-item">
            потребовать удаления данных;
          </li>
          <li className="section-block__list-item">ограничить обработку;</li>
          <li className="section-block__list-item">
            возразить против обработки;
          </li>
          <li className="section-block__list-item">
            получить данные в переносимом формате;
          </li>
          <li className="section-block__list-item">
            отозвать ранее данное согласие.
          </li>
        </ul>

        <p className="section-block__text">
          Для реализации своих прав напиши по адресу{" "}
          <a href="mailto:[EMAIL]" className="underline">
            [EMAIL]
          </a>
          .
        </p>

        <p className="section-block__text">
          Перед выполнением запроса мы можем попросить подтвердить личность,
          чтобы не передать или не удалить данные по запросу постороннего
          человека.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          12. Право подать жалобу
        </h2>

        <p className="section-block__text">
          Если пользователь считает, что его данные обрабатываются с нарушением
          закона, он может обратиться в надзорный орган.
        </p>

        <address className="section-block__text not-italic">
          Der Landesbeauftragte für Datenschutz und Informationsfreiheit
          <br />
          Georgstraße 122–124
          <br />
          27570 Bremerhaven
          <br />
          Email:{" "}
          <a href="mailto:office@datenschutz.bremen.de" className="underline">
            office@datenschutz.bremen.de
          </a>
        </address>

        <p className="section-block__text">
          Онлайн-форма для подачи жалобы:{" "}
          <a
            href="https://www.datenschutz.bremen.de/wir-ueber-uns/online-meldungen/beschwerdeformular-15253"
            target="_blank"
            rel="noreferrer"
            className="underline"
          >
            datenschutz.bremen.de
          </a>
          .
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">13. Защита данных</h2>

        <p className="section-block__text">
          Мы принимаем разумные технические и организационные меры для защиты
          данных от потери, неправомерного доступа, изменения и раскрытия.
        </p>

        <p className="section-block__text">
          Доступ к заявкам ограничивается администраторами, которым он необходим
          для рассмотрения и организации участия в клубе.
        </p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">
          14. Изменение политики
        </h2>

        <p className="section-block__text">
          Эта политика может обновляться при изменении сайта, используемых
          сервисов или требований законодательства.
        </p>

        <p className="section-block__text">
          Актуальная версия всегда публикуется на этой странице с указанием даты
          последнего обновления.
        </p>
      </section>
    </main>
  );
}
