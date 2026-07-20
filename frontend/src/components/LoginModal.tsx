"use client";

import {FormEvent, useState} from "react";
import {Loader2, Sun, X} from "lucide-react";
import {ApiError, type ApiFieldErrors} from "@/lib/api";

interface LoginModalProps {
    onClose: () => void;
    onLogin: (
        email: string,
        password: string,
        rememberMe: boolean
    ) => Promise<void>;

    onRegister: (
        regEmail: string,
        regFirstName: string,
        regLastName: string,
        regPassword: string,
        regPasswordConfirm: string
    ) => Promise<void>;
}

const emptyRegisterErrors = {
    general: [] as string[],
    fields: {} as ApiFieldErrors,
};

export function LoginModal({onClose, onLogin, onRegister}: LoginModalProps) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [rememberMe, setRememberMe] = useState(true);
    const [loginError, setLoginError] = useState<string | null>(null);
    const [registerErrors, setRegisterErrors] = useState(emptyRegisterErrors);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Register state
    const [regEmail, setRegEmail] = useState("");
    const [regFirstName, setRegFirstName] = useState("");
    const [regLastName, setRegLastName] = useState("");
    const [regPassword, setRegPassword] = useState("");
    const [regPasswordConfirm, setRegPasswordConfirm] = useState("");

    const [mode, setMode] = useState<"login" | "register">("login");

    const switchMode = (nextMode: "login" | "register") => {
        setMode(nextMode);
        setLoginError(null);
        setRegisterErrors(emptyRegisterErrors);
    };

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault();
        setLoginError(null);
        setIsSubmitting(true);

        try {
            await onLogin(email.trim(), password, rememberMe);
        } catch (err) {
            const message =
                err instanceof ApiError
                    ? [...err.generalErrors, ...Object.values(err.fieldErrors).flat()].join(" ") ||
                    err.message
                    : "Anmeldung fehlgeschlagen. Bitte versuchen Sie es erneut.";
            setLoginError(message);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleRegister = async (event: FormEvent) => {
        event.preventDefault();
        setRegisterErrors(emptyRegisterErrors);
        setIsSubmitting(true);

        try {
            await onRegister(
                regEmail.trim(),
                regFirstName.trim(),
                regLastName.trim(),
                regPassword,
                regPasswordConfirm
            );
        } catch (err) {
            if (err instanceof ApiError) {
                setRegisterErrors({
                    general: err.generalErrors,
                    fields: err.fieldErrors,
                });
            } else {
                setRegisterErrors({
                    general: ["Registrierung fehlgeschlagen. Bitte versuchen Sie es erneut."],
                    fields: {},
                });
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 p-4 bg-black/50 backdrop-blur-sm flex items-center justify-center">
            <div className="bg-bg border border-border rounded-2xl w-full max-w-md shadow-2xl">
                <div className="flex justify-end p-6 border-b border-border">
                        <button
                            type="button"
                            onClick={onClose}
                            className="button-gray-rounded"
                            disabled={isSubmitting}
                        >
                            <X size={18}/>
                        </button>
                    </div>
                    {/* Tab switcher */}
                    <div className="flex border-b border-border">
                        <button
                            onClick={() => switchMode("login")}
                            className={`flex-1 py-3 text-sm font-semibold transition-colors ${mode === "login" ? "text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-foreground"}`}
                        >
                            Вход
                        </button>
                        <button
                            onClick={() => switchMode("register")}
                            className={`flex-1 py-3 text-sm font-semibold transition-colors ${mode === "register" ? "text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-foreground"}`}
                        >
                            Регистрация
                        </button>
                    </div>
                    {mode === "login" && (
                        <form onSubmit={handleSubmit} className="p-6 space-y-4">
                            <div>
                                <label
                                    htmlFor="login-email"
                                    className="text-foreground text-sm font-semibold block mb-1.5"
                                >
                                    Электронная почта
                                </label>
                                <input
                                    id="login-email"
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    required
                                    autoComplete="email"
                                    disabled={isSubmitting}
                                    className="w-full px-3 py-2.5 bg-input-background border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-60"
                                />
                            </div>
                            <div>
                                <label
                                    htmlFor="login-password"
                                    className="text-foreground text-sm font-semibold block mb-1.5"
                                >
                                    Пароль
                                </label>
                                <input
                                    id="login-password"
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                    autoComplete="current-password"
                                    disabled={isSubmitting}
                                    className="w-full px-3 py-2.5 bg-input-background border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-60"
                                />
                            </div>
                            <div className="flex items-center justify-between text-xs">
                                <label className="flex items-center gap-2 text-muted-foreground cursor-pointer">
                                    <input
                                        type="checkbox"
                                        className="rounded border-border"
                                        checked={rememberMe}
                                        onChange={(e) => setRememberMe(e.target.checked)}
                                        disabled={isSubmitting}
                                    />
                                    Запомнить меня
                                </label>
                                <a href="#" className="text-accent hover:underline">
                                    Забыли пароль?
                                </a>
                            </div>

                            {loginError && (
                                <div
                                    className="p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-xs text-destructive">
                                    {loginError}
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={isSubmitting}
                                className="button-gray-rounded w-full py-3 flex items-center justify-center gap-2"
                                style={{fontFamily: "var(--font-display)"}}
                            >
                                {isSubmitting ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin"/>
                                        Подождите…
                                    </>
                                ) : (
                                    "Войти"
                                )}
                            </button>
                            <p className="text-center text-muted-foreground text-xs">
                                Нет аккаунта?{" "}
                                <a href="#"
                                   onClick={() => switchMode("register")}
                                   className="text-accent font-semibold hover:underline">
                                    Регистрация
                                </a>
                            </p>
                        </form>
                    )}
                    {mode === "register" && (
                        <form onSubmit={handleRegister} className="p-6 space-y-4">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label
                                        htmlFor="register-first-name"
                                        className="text-foreground text-sm font-semibold block mb-1.5"
                                    >
                                        Имя
                                    </label>
                                    <input
                                        id="register-first-name"
                                        type="text"
                                        value={regFirstName}
                                        onChange={(e) => setRegFirstName(e.target.value)}
                                        required
                                        autoComplete="given-name"
                                        disabled={isSubmitting}
                                        className="w-full px-3 py-2.5 bg-input-background border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-60"
                                    />
                                    <FieldErrors messages={registerErrors.fields.first_name}/>
                                </div>
                                <div>
                                    <label
                                        htmlFor="register-last-name"
                                        className="text-foreground text-sm font-semibold block mb-1.5"
                                    >
                                        Фамилия
                                    </label>
                                    <input
                                        id="register-last-name"
                                        type="text"
                                        value={regLastName}
                                        onChange={(e) => setRegLastName(e.target.value)}
                                        required
                                        autoComplete="family-name"
                                        disabled={isSubmitting}
                                        className="w-full px-3 py-2.5 bg-input-background border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-60"
                                    />
                                    <FieldErrors messages={registerErrors.fields.last_name}/>
                                </div>
                            </div>
                            <div>
                                <label
                                    htmlFor="register-email"
                                    className="text-foreground text-sm font-semibold block mb-1.5"
                                >
                                    Адрес электронной почты
                                </label>
                                <input
                                    id="register-email"
                                    type="email"
                                    value={regEmail}
                                    onChange={(e) => setRegEmail(e.target.value)}
                                    required
                                    autoComplete="email"
                                    disabled={isSubmitting}
                                    className="w-full px-3 py-2.5 bg-input-background border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-60"
                                />
                                <FieldErrors messages={registerErrors.fields.email}/>
                            </div>
                            <div>
                                <label
                                    htmlFor="register-password"
                                    className="text-foreground text-sm font-semibold block mb-1.5"
                                >
                                    Пароль
                                </label>
                                <input
                                    id="register-password"
                                    type="password"
                                    value={regPassword}
                                    onChange={(e) => setRegPassword(e.target.value)}
                                    required
                                    autoComplete="new-password"
                                    disabled={isSubmitting}
                                    className="w-full px-3 py-2.5 bg-input-background border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-60"
                                />
                                <FieldErrors messages={registerErrors.fields.password}/>
                            </div>
                            <div>
                                <label
                                    htmlFor="register-password-verify"
                                    className="text-foreground text-sm font-semibold block mb-1.5"
                                >
                                    Подтверждение пароля
                                </label>
                                <input
                                    id="register-password-verify"
                                    type="password"
                                    value={regPasswordConfirm}
                                    onChange={(e) => setRegPasswordConfirm(e.target.value)}
                                    required
                                    autoComplete="new-password"
                                    disabled={isSubmitting}
                                    className="w-full px-3 py-2.5 bg-input-background border border-border rounded-lg text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-60"
                                />
                                <FieldErrors messages={registerErrors.fields.password_confirm}/>
                            </div>
                            <div className="flex items-center justify-between text-xs">
                                <p className="text-muted-foreground text-xs text-center">
                                    Регистрируясь вы подтверждаете наши условия пользования{" "}
                                    <a href="#" className="text-accent hover:underline">AGB</a> und{" "}
                                    <a href="#" className="text-accent hover:underline">Datenschutzerklärung</a>.
                                </p>
                            </div>

                            {registerErrors.general.length > 0 && (
                                <div
                                    className="p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-xs text-destructive">
                                    <ErrorList messages={registerErrors.general}/>
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={isSubmitting}
                                className="button-gray-rounded w-full py-3 flex items-center justify-center gap-2"
                                style={{fontFamily: "var(--font-display)"}}
                            >
                                {isSubmitting ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin"/>
                                        Подождите…
                                    </>
                                ) : (
                                    "Создать аккаунт"
                                )}
                            </button>
                        </form>
                    )}
                </div>
            </div>
        
    );
}

function FieldErrors({messages}: { messages?: string[] }) {
    if (!messages?.length) return null;

    return (
        <ul className="mt-1.5 space-y-1">
            {messages.map((message, index) => (
                <li key={`${message}-${index}`} className="text-xs text-destructive">
                    {message}
                </li>
            ))}
        </ul>
    );
}

function ErrorList({messages}: { messages: string[] }) {
    if (messages.length === 0) return null;

    if (messages.length === 1) {
        return <p>{messages[0]}</p>;
    }

    return (
        <ul className="list-disc pl-4 space-y-1">
            {messages.map((message, index) => (
                <li key={`${message}-${index}`}>{message}</li>
            ))}
        </ul>
    );
}
