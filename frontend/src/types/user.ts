export interface User {
  id: number;
  customer_number: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name?: string;
  is_active: boolean;
  is_staff: boolean;
}

export function getUserDisplayName(user: User): string {
  const name = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
  return name || user.email;
}

export function getUserInitials(user: User): string {
  const name = getUserDisplayName(user);
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

export interface TokenPair {
  access: string;
  refresh: string;
}
