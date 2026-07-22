"use client";

export default function ContactPage() {
  return (
    <div className="max-w-5xl min-h-screen flex flex-col items-start px-4 text-left">
      <section className="section-block">
        <h1 className="section-block__title font-black">Impressum</h1>

        <p className="section-block__text">Angaben gemäß § 5 DDG</p>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">Verantwortlich</h2>

        <address className="section-block__text not-italic">
          [VORNAME NACHNAME]
          <br />
          Privater Betreiber des Community-Projekts „Черёмушки“
          <br />
          [STRASSE UND HAUSNUMMER]
          <br />
          [POSTLEITZAHL UND ORT]
          <br />
          Deutschland
        </address>
      </section>

      <section className="section-block">
        <h2 className="section-block__title font-black">Kontakt</h2>

        <p className="section-block__text">
          E-Mail:{" "}
          <a href="mailto:[EMAIL]" className="underline">
            [EMAIL]
          </a>
        </p>
      </section>
    </div>
  );
}
