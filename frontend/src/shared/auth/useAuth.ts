/**
 * useAuth — anonymous email-based identity.
 *
 * Identity is established when a user registers via the waitlist form (Supabase).
 * The email is persisted in localStorage so it survives page reloads.
 *
 * No passwords, no sessions, no JWT — just an email stored locally that's
 * used as the portfolio key on the backend.
 */

const STORAGE_KEY = 'geotrade_user_email'

export function getStoredEmail(): string | null {
    try {
        return localStorage.getItem(STORAGE_KEY)
    } catch {
        return null
    }
}

export function setStoredEmail(email: string): void {
    try {
        localStorage.setItem(STORAGE_KEY, email.toLowerCase().trim())
    } catch {
        // localStorage unavailable (private mode etc.) — fail silently
    }
}

export function clearStoredEmail(): void {
    try {
        localStorage.removeItem(STORAGE_KEY)
    } catch {
        // ignore
    }
}

export function useAuth() {
    const email = getStoredEmail()
    return {
        email,
        isRegistered: email !== null && email.length > 0,
    }
}
