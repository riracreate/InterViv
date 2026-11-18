/** Use only the account overview's real, bounded session history. */
export function buildProgressInsights(history = [], now = new Date()) {
  const valid = history.flatMap(session => {
    if (!session?.created_at) return [];
    const date = new Date(session.created_at);
    return Number.isFinite(date.getTime()) ? [{ ...session, date }] : [];
  });
  const trend = valid
    .filter(session => session.status === 'completed' && session.round_types?.length === 1
      && typeof session.average_score === 'number' && Number.isFinite(session.average_score))
    .sort((a, b) => a.date - b.date).slice(-6);
  const counts = new Map();
  for (const session of valid) {
    const day = session.date.toISOString().slice(0, 10);
    counts.set(day, (counts.get(day) || 0) + 1);
  }
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const calendar = Array.from({ length: 84 }, (_, index) => {
    const date = new Date(today - (83 - index) * 86400000).toISOString().slice(0, 10);
    return { date, count: counts.get(date) || 0 };
  });
  return { trend, calendar };
}
