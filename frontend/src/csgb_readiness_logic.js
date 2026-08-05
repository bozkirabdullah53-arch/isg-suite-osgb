export function normalizePriorityItem(raw) {
  const item = raw && typeof raw === 'object' ? raw : {};
  return {
    code: String(item.code || ''),
    title: String(item.title || 'İsimsiz denetim kalemi'),
    status: item.status === 'partial' ? 'partial' : 'missing',
    detail: String(item.detail || 'Kanıt veya kayıt eksik.'),
    actionLabel: String(item.action_label || 'ÇSGB paketinde inceleyin'),
    actionModule: String(item.action_module || 'csgb_audit'),
    contextReview: Boolean(item.context_review),
  };
}

export function buildCsgbReadinessView(csgbItem) {
  const item = csgbItem && typeof csgbItem === 'object' ? csgbItem : {};
  const priorities = Array.isArray(item.priority_items)
    ? item.priority_items.map(normalizePriorityItem)
    : [];
  const contextualNotes = Array.isArray(item.contextual_notes)
    ? item.contextual_notes.map((note) => ({
        code: String(note?.code || ''),
        title: String(note?.title || 'Bağlamsal inceleme'),
        detail: String(note?.detail || ''),
        legalBasis: String(note?.legal_basis || ''),
      }))
    : [];

  return {
    readinessPct: Number.isFinite(Number(item.readiness_pct)) ? Number(item.readiness_pct) : 0,
    priorityCount: Number.isFinite(Number(item.gap_count))
      ? Number(item.gap_count)
      : priorities.length,
    priorities,
    contextualNotes,
    scoreChanged: Boolean(item.score_changed),
    hasDetails: priorities.length > 0 || contextualNotes.length > 0,
  };
}
