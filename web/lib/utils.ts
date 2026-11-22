import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format UI labels from enum keys without changing their underlying values. */
export function titleLabel(value: string): string {
  const label = value.replaceAll("_", " ").replace(
    /\b(ebitda|usd|fx|id|ev|ltm)\b/gi,
    (acronym) => acronym.toUpperCase(),
  );
  return label.replace(/\b[a-z]+\b/gi, (word, offset: number) =>
    offset > 0 && /^(a|an|the|and|or|of|by|to|with|in|per)$/.test(word)
      ? word
      : word.charAt(0).toUpperCase() + word.slice(1),
  );
}
