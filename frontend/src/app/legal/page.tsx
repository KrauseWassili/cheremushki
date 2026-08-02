"use client";

export default function ContactPage() {
  return (
    <main className="mx-auto w-full max-w-3xl py-4">
      <header className="mx-auto mb-10 max-w-3xl text-center">
        <h1 className="mt-3 text-4xl font-black tracking-tight">Правовая информация</h1>

        <p className="section-block__text">Сведения согласно § 5 DDG</p>
      </header>

      <section className="section-block">
        <h2 className="section-block__title font-black">Ответственный</h2>

        <address className="section-block__text not-italic">
          [ИМЯ И ФАМИЛИЯ]
          <br />
          Частный организатор проекта сообщества «Черёмушки»
          <br />
          [УЛИЦА И НОМЕР ДОМА]
          <br />
          [ИНДЕКС И ГОРОД]
          <br />
          Германия
        </address>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">Контакты</h2>

        <p className="section-block__text">
          Почта:{" "}
          <a href="mailto:[EMAIL]" className="underline">
            [EMAIL]
          </a>
        </p>
      </section>
    </main>
  );
}
