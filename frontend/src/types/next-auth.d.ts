// eslint-disable-next-line @typescript-eslint/no-unused-vars
import NextAuth from "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id?: number | null;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      googleId?: string | null;
      role?: string | null;
    };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id?: number | null;
    googleId?: string | null;
    role?: string | null;
  }
}
