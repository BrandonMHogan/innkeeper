import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type WithoutChild<T> = T extends { child?: any } ? Omit<T, "child"> : T;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type WithoutChildren<T> = T extends { children?: any } ? Omit<T, "children"> : T;
export type WithoutChildrenOrChild<T> = WithoutChildren<WithoutChild<T>>;
export type WithElementRef<T, U extends HTMLElement = HTMLElement> = T & { ref?: U | null };

/**
 * Formats a byte count as a human-readable string (B/KB/MB/GB), one decimal
 * place, at powers of 1024. Used by every byte-value-rendering surface in
 * Phase 3 (live traffic feed, bandwidth charts, destinations breakdown) per
 * 03-UI-SPEC.md's numeric convention — byte values are never shown as raw
 * integers.
 */
export function formatBytes(n: number): string {
	if (!Number.isFinite(n) || n < 0) return "0 B";
	const units = ["B", "KB", "MB", "GB"];
	let value = n;
	let unitIndex = 0;
	while (value >= 1024 && unitIndex < units.length - 1) {
		value /= 1024;
		unitIndex += 1;
	}
	const formatted = unitIndex === 0 ? `${Math.round(value)}` : value.toFixed(1);
	return `${formatted} ${units[unitIndex]}`;
}
