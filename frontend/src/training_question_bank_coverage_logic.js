export const SMART_TOPIC_COUNT = 5;
export const SMART_QUESTION_COUNT = 15;

function normalizedTopics(sector) {
  return Array.isArray(sector?.topics)
    ? sector.topics.map((topic) => String(topic || '').trim()).filter(Boolean)
    : [];
}

export function buildSmartSectorIndex(sectors = []) {
  const byCode = new Map();
  const byNace = new Map();
  for (const sector of Array.isArray(sectors) ? sectors : []) {
    const code = String(sector?.code || '').trim();
    const nace = String(sector?.nace || '').trim();
    if (code) byCode.set(code, sector);
    if (nace) byNace.set(nace, sector);
  }
  return {byCode, byNace};
}

export function smartReadinessForItem(item, index) {
  const code = String(item?.code || '').trim();
  const nace = String(item?.nace || '').trim();
  const sector = index?.byCode?.get(code) || index?.byNace?.get(nace) || null;
  const topics = normalizedTopics(sector);
  const ready = topics.length === SMART_TOPIC_COUNT;
  return {
    ready,
    topicCount: topics.length,
    questionCount: ready ? SMART_QUESTION_COUNT : 0,
  };
}

export function smartCoverageSummary(sectors = []) {
  const naceRows = (Array.isArray(sectors) ? sectors : []).filter((sector) => String(sector?.nace || '').trim());
  const readyCount = naceRows.reduce(
    (total, sector) => total + Number(normalizedTopics(sector).length === SMART_TOPIC_COUNT),
    0,
  );
  return {
    catalogCount: naceRows.length,
    readyCount,
    reviewCount: Math.max(0, naceRows.length - readyCount),
  };
}

export function coveragePagination(report, fallbackLimit = 50) {
  const total = Math.max(0, Number(report?.items_total || 0));
  const limit = Math.max(1, Number(report?.limit || fallbackLimit || 50));
  const offset = Math.max(0, Number(report?.offset || 0));
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.min(totalPages, Math.floor(offset / limit) + 1);
  return {
    total,
    limit,
    offset,
    totalPages,
    currentPage,
    hasPrevious: offset > 0,
    hasNext: offset + limit < total,
    previousOffset: Math.max(0, offset - limit),
    nextOffset: offset + limit,
  };
}
