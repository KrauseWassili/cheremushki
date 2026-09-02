"use client";

import Link from "next/link";
import Image from "next/image";
import {usePathname} from "next/navigation";
import {useEffect, useRef, useState} from "react";
import {useApp} from "@/providers/AppProvider";
import {PROFILE_UPDATED_EVENT} from "@/lib/profile-events";
import {fetchMyProfile} from "@/lib/profiles";
import {useEscapeKey} from "@/lib/use-escape-key";
import {LogIn, Menu, X} from "lucide-react";
import {getUserDisplayName, getUserInitials} from "@/types/user";
import {AccountDropdown} from "./header/account-dropdown";
import {MobileMenu} from "./header/mobile-menu";
import type {HeaderNavItem} from "./header/types";

type HeaderAvatar = {
    url?: string;
    originalUrl?: string;
    positionX?: number;
    positionY?: number;
    scale?: number;
    cropSize?: number;
};

export default function Header() {
    const pathname = usePathname();
    const {user, isLoggedIn, logout, openLogin} = useApp();
    const [isProfileReady, setIsProfileReady] = useState(false);
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
    const [accountAvatar, setAccountAvatar] = useState<HeaderAvatar>({});
    const navRef = useRef<HTMLElement>(null);
    const accountMenuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!isLoggedIn) {
            setIsProfileReady(false);
            setAccountAvatar({});
            return;
        }

        let cancelled = false;

        async function loadStatus() {
            try {
                const api = await fetchMyProfile();
                if (!cancelled) {
                    // directory_ready kommt aus dem Backend und ist maßgeblich – es
                    // schließt user.is_active ein, was aus den Profilfeldern allein nicht hervorgeht.
                    setIsProfileReady(Boolean(api.directory_ready));
                    setAccountAvatar({
                        url: api.avatar_url ?? undefined,
                        originalUrl: api.avatar_original_url ?? undefined,
                        positionX: api.avatar_position_x,
                        positionY: api.avatar_position_y,
                        scale: api.avatar_scale,
                        cropSize: api.avatar_crop_size,
                    });
                }
            } catch {
                if (!cancelled) {
                    setIsProfileReady(false);
                    setAccountAvatar({});
                }
            }
        }

        loadStatus();

        function handleProfileUpdated() {
            void loadStatus();
        }

        window.addEventListener(PROFILE_UPDATED_EVENT, handleProfileUpdated);

        return () => {
            cancelled = true;
            window.removeEventListener(PROFILE_UPDATED_EVENT, handleProfileUpdated);
        };
    }, [isLoggedIn, pathname]);

    useEffect(() => {
        setIsMenuOpen(false);
        setIsAccountMenuOpen(false);
    }, [pathname, isLoggedIn]);

    useEscapeKey(isMenuOpen || isAccountMenuOpen, () => {
        setIsMenuOpen(false);
        setIsAccountMenuOpen(false);
    });

    useEffect(() => {
        if (!isMenuOpen) return;

        function handlePointerDown(event: PointerEvent) {
            const target = event.target;
            if (!(target instanceof Node)) return;
            if (navRef.current?.contains(target)) return;

            setIsMenuOpen(false);
        }

        document.addEventListener("pointerdown", handlePointerDown);
        return () => document.removeEventListener("pointerdown", handlePointerDown);
    }, [isMenuOpen]);

    useEffect(() => {
        if (!isAccountMenuOpen) return;

        function handlePointerDown(event: PointerEvent) {
            const target = event.target;
            if (!(target instanceof Node)) return;
            if (accountMenuRef.current?.contains(target)) return;

            setIsAccountMenuOpen(false);
        }

        document.addEventListener("pointerdown", handlePointerDown);
        return () => document.removeEventListener("pointerdown", handlePointerDown);
    }, [isAccountMenuOpen]);

    const accountName = user ? getUserDisplayName(user) : "";
    const accountInitials = user ? getUserInitials(user) : "";

    const navItems: HeaderNavItem[] = [
        {href: "/", label: "Приветствие"},
        {href: "/project", label: "О проекте"},
        ...(isLoggedIn ? [{href: "/members", label: "Участники"}] : []),
    ];

    const getLinkClassName = (href: string) => {
        const isActive = pathname === href;

        return [
            "inline-flex h-9 cursor-pointer items-center whitespace-nowrap rounded-md px-3 text-base font-medium no-underline transition-colors",
            isActive
                ? "bg-header-active-bg !text-header-active-text"
                : "!text-header-link hover:bg-header-hover-bg hover:!text-header-link-hover",
        ].join(" ");
    };

    const getMobileLinkClassName = (href: string) => {
        const isActive = pathname === href;

        return [
            "block rounded-xl px-3 py-2 text-base no-underline transition-colors",
            isActive
                ? "bg-header-active-bg !text-header-active-text"
                : "!text-header-link hover:bg-header-hover-bg hover:!text-header-link-hover",
        ].join(" ");
    };

    return (
        <header className="fixed left-0 top-0 z-40 h-14 w-full bg-header-bg text-header-link-hover">
            <nav ref={navRef} className="relative mx-auto h-full w-full px-4">
                <div
                    className="grid h-full grid-cols-[1fr_auto] items-center gap-4 min-[900px]:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
                    <div className="flex items-center justify-start">
                        <Link
                            href="/"
                            aria-label="Черемушки"
                            className="inline-flex items-center no-underline"
                        >
                            <Image
                                src="/brand-mark-header.webp"
                                alt=""
                                width={48}
                                height={48}
                                priority
                                className="size-12 object-contain drop-shadow-[0_3px_3px_color-mix(in_srgb,var(--palette-ink)_90%,transparent)]"
                            />
                        </Link>
                    </div>

                    <div className="hidden min-w-0 items-center justify-center gap-2 min-[900px]:flex">
                        {navItems.map((item) => (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={getLinkClassName(item.href)}
                            >
                                {item.label}
                            </Link>
                        ))}
                    </div>

                    <div className="hidden items-center justify-end gap-2 min-[900px]:flex">
                        {isLoggedIn ? (
                            <div ref={accountMenuRef} className="relative flex h-10 items-center">
                                <AccountDropdown
                                    avatarUrl={accountAvatar.url}
                                    avatarOriginalUrl={accountAvatar.originalUrl}
                                    avatarPositionX={accountAvatar.positionX}
                                    avatarPositionY={accountAvatar.positionY}
                                    avatarScale={accountAvatar.scale}
                                    avatarCropSize={accountAvatar.cropSize}
                                    name={accountName}
                                    initials={accountInitials}
                                    email={user?.email}
                                    isOpen={isAccountMenuOpen}
                                    isProfileReady={isProfileReady}
                                    onToggle={() =>
                                        setIsAccountMenuOpen((current) => !current)
                                    }
                                    onLogout={() => {
                                        setIsAccountMenuOpen(false);
                                        void logout();
                                    }}
                                    getMenuLinkClassName={getMobileLinkClassName}
                                />
                            </div>
                        ) : (
                            <>
                                <button
                                    type="button"
                                    onClick={() => openLogin("login")}
                                    className="button-flat inline-flex h-9 cursor-pointer items-center gap-2 whitespace-nowrap rounded-md px-3 text-base font-medium !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
                                >
                                    <span>Войти</span>
                                    <LogIn size={16}/>
                                </button>
                                <button
                                    type="button"
                                    onClick={() => openLogin("register")}
                                    className="button-flat h-9 cursor-pointer whitespace-nowrap rounded-md px-3 text-base font-medium !text-header-link transition-colors hover:bg-header-hover-bg hover:!text-header-link-hover"
                                >
                                    Зарегистрироваться
                                </button>
                            </>
                        )}
                    </div>

                    <div className="flex items-center justify-end min-[900px]:hidden">
                        <button
                            type="button"
                            aria-label={isMenuOpen ? "Закрыть меню" : "Открыть меню"}
                            aria-expanded={isMenuOpen}
                            onClick={() => setIsMenuOpen((current) => !current)}
                            className="button-flat inline-flex size-9 items-center justify-center rounded-xl border border-header-link/30 text-header-link transition hover:bg-header-hover-bg hover:text-header-link-hover"
                        >
                            {isMenuOpen ? <X size={20}/> : <Menu size={20}/>}
                        </button>
                    </div>
                </div>

                {isMenuOpen && (
                    <MobileMenu
                        avatarUrl={accountAvatar.url}
                        avatarOriginalUrl={accountAvatar.originalUrl}
                        avatarPositionX={accountAvatar.positionX}
                        avatarPositionY={accountAvatar.positionY}
                        avatarScale={accountAvatar.scale}
                        avatarCropSize={accountAvatar.cropSize}
                        name={accountName}
                        initials={accountInitials}
                        email={user?.email}
                        isLoggedIn={isLoggedIn}
                        isProfileReady={isProfileReady}
                        navItems={navItems}
                        onLogin={() => {
                            setIsMenuOpen(false);
                            openLogin("login");
                        }}
                        onRegister={() => {
                            setIsMenuOpen(false);
                            openLogin("register");
                        }}
                        onLogout={() => {
                            setIsMenuOpen(false);
                            void logout();
                        }}
                        getMenuLinkClassName={getMobileLinkClassName}
                    />
                )}
            </nav>
        </header>
    );
}
