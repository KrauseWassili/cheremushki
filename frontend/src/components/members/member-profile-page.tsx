"use client";

import { useEffect, useState } from "react";
import type { MemberProfile } from "@/types/member";
import { MemberProfileView } from "./member-profile";
import { MemberProfileEditor } from "./member-profile-editor";

type MemberProfilePageProps = {
  initialMember: MemberProfile;
  canEdit: boolean;
};

export function MemberProfilePage({
  initialMember,
  canEdit,
}: MemberProfilePageProps) {
  const storageKey = `mock-member-${initialMember.id}`;

  const [member, setMember] = useState(initialMember);
  const [isEditing, setIsEditing] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const savedMember = window.localStorage.getItem(storageKey);

    if (savedMember) {
      try {
        setMember(JSON.parse(savedMember) as MemberProfile);
      } catch {
        window.localStorage.removeItem(storageKey);
      }
    }

    setIsLoaded(true);
  }, [storageKey]);

  function handleSave(updatedMember: MemberProfile) {
    setMember(updatedMember);
    window.localStorage.setItem(
      storageKey,
      JSON.stringify(updatedMember),
    );
    setIsEditing(false);
  }

  function handleReset() {
    setMember(initialMember);
    window.localStorage.removeItem(storageKey);
    setIsEditing(false);
  }

  if (!isLoaded) {
    return (
      <div className="rounded-3xl border border-border p-8">
        Загрузка профиля…
      </div>
    );
  }

  if (isEditing) {
    return (
      <MemberProfileEditor
        member={member}
        onSave={handleSave}
        onCancel={() => setIsEditing(false)}
      />
    );
  }

  return (
    <>
      {canEdit && (
        <div className="mb-5 flex flex-wrap justify-end gap-3">
          <button
            type="button"
            onClick={handleReset}
            className="rounded-xl border border-border px-4 py-2.5 text-sm font-bold hover:bg-muted"
          >
            Сбросить изменения
          </button>

          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className="rounded-xl bg-foreground px-4 py-2.5 text-sm font-bold text-background"
          >
            Редактировать профиль
          </button>
        </div>
      )}

      <MemberProfileView member={member} />
    </>
  );
}