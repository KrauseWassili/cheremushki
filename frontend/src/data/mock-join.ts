import type { JoinDemoState } from "@/types/join";

export const initialJoinDemoState: JoinDemoState = {
  application: {
    email: "anna.volkova@example.de",
    fullName: "Анна Волкова",
    city: "Бремен",
    profession: "Product Design",
    position: "Senior Product Designer",
    company: "NordPay GmbH",

    bio: "Я проектирую цифровые продукты и помогаю командам разбираться со сложными пользовательскими сценариями. В Германии живу четыре года.",
    motivation:
      "Хочу познакомиться с русскоязычными специалистами из Бремена и окрестностей, обмениваться опытом и участвовать в небольших профессиональных встречах.",
    contribution:
      "Могу помогать с разбором дизайнерских портфолио, подготовкой к собеседованиям и вопросами работы в немецких продуктовых командах.",
    lookingFor:
      "Ищу людей для небольших дизайн-митапов, совместных проектов и поездок по северу Германии.",

    linkedinUrl: "https://www.linkedin.com/in/anna-volkova",
    websiteUrl: "https://anna-volkova.example.com",
    telegramUsername: "anna_volkova",
    referredBy: "О клубе рассказал коллега",

    rulesAccepted: true,
    privacyAccepted: true,
  },

  status: "under_review",

  adminMessage:
    "Расскажи, пожалуйста, немного подробнее о своём профессиональном опыте и добавь ссылку на LinkedIn или личный сайт.",
};