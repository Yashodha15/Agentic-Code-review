// Demo 03: TypeScript contract and time-unit mismatch.
export interface Session {
  userId: string;
  expiresAt: number;
}

export function isSessionActive(session: Session): boolean {
  return session.expiresAt > Date.now();
}

