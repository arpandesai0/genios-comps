import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format UI labels from enum keys without changing their underlying values. */
export function sentenceLabel(value: string): string {
  const label = value.replaceAll("_", " ").replace(
    /\b(ebitda|usd|fx|id|ev|ltm)\b/gi,
    (acronym) => acronym.toUpperCase(),
  );
  return label.charAt(0).toUpperCase() + label.slice(1);
}
