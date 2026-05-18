const DATA_PATHS = [
  "data/policy_frontier.json",
  "./data/policy_frontier.json",
  "/econ-policy-frontier-tracker/data/policy_frontier.json",
];

const state = {
  payload: null,
  tracker: null,
  sources: [],
  topics: [],
};

const els = {
  updateTime: document.getElementById("update-time"),
  refreshBtn: document.getElementById("refresh-btn"),
  topicFilter: document.getElementById("topic-filter"),
  sourceTypeFilter: document.getElementById("source-type-filter"),
  sourceFilter: document.getElementById("source-filter"),
  searchInput: document.getElementById("search-input"),
  summaryCards: document.getElementById("summary-cards"),
  topicStrip: document.getElementById("topic-strip"),
  errorBox: document.getElementById("error-box"),
  sourceList: document.getElementById("source-list"),
};

function escapeHtml(input) {
  return String(input || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalize(input) {
  return String(input || "").toLowerCase().trim();
}

function getTracker(payload) {
  return payload.policy_frontier_tracker || payload.tracker || {};
}

function getSources(tracker) {
  if (Array.isArray(tracker.sources)) {
    return tracker.sources;
  }

  const journals = Array.isArray(tracker.journals) ? tracker.journals : [];
  const nber = tracker.nber ? [tracker.nber] : [];
  return [...journals, ...nber];
}

function paperMatchesFilter(paper) {
  const selectedTopic = els.topicFilter.value;
  const keyword = normalize(els.searchInput.value);

  if (selectedTopic) {
    const topics = Array.isArray(paper.matched_topics) ? paper.matched_topics : [];
    if (!topics.includes(selectedTopic)) {
      return false;
    }
  }

  if (!keyword) {
    return true;
  }

  const haystack = normalize([
    paper.title_en,
    paper.title_zh,
    paper.abstract_en,
    paper.abstract_zh,
    paper.authors,
    paper.date,
    paper.matched_topics,
  ].join(" "));

  return haystack.includes(keyword);
}

function sourceMatchesFilter(source) {
  const selectedType = els.sourceTypeFilter.value;
  const selectedSource = els.sourceFilter.value;

  if (selectedType && source.source_type !== selectedType) {
    return false;
  }

  if (selectedSource && source.name !== selectedSource) {
    return false;
  }

  return true;
}

function filteredSources() {
  return state.sources.filter(sourceMatchesFilter);
}

function matchingPapersFor(source) {
  const papers = Array.isArray(source.papers) ? source.papers : [];
  return papers.filter(paperMatchesFilter);
}

function fillFilterOptions() {
  els.topicFilter.innerHTML = `<option value="">全部主题</option>`;
  for (const topic of state.topics) {
    els.topicFilter.insertAdjacentHTML("beforeend", `<option value="${escapeHtml(topic)}">${escapeHtml(topic)}</option>`);
  }

  els.sourceFilter.innerHTML = `<option value="">全部期刊/来源</option>`;
  for (const source of state.sources) {
    els.sourceFilter.insertAdjacentHTML(
      "beforeend",
      `<option value="${escapeHtml(source.name || "")}">${escapeHtml(source.name || "")}</option>`
    );
  }
}

function renderSummary(sources) {
  const allPapers = sources.flatMap((source) => matchingPapersFor(source));
  const totalMatched = sources.reduce((sum, source) => sum + (Array.isArray(source.papers) ? source.papers.length : 0), 0);
  const totalScanned = sources.reduce((sum, source) => {
    return sum + Number(source.total_in_issue || source.total_recent_considered || 0);
  }, 0);
  const errors = sources.filter((source) => source.error).length;

  els.summaryCards.innerHTML = `
    <article class="summary-card">
      <div class="summary-label">追踪来源</div>
      <div class="summary-value">${sources.length}</div>
    </article>
    <article class="summary-card">
      <div class="summary-label">当前筛选命中</div>
      <div class="summary-value">${allPapers.length}</div>
    </article>
    <article class="summary-card">
      <div class="summary-label">主题总命中</div>
      <div class="summary-value">${totalMatched}</div>
    </article>
    <article class="summary-card">
      <div class="summary-label">扫描条目</div>
      <div class="summary-value">${totalScanned}</div>
    </article>
  `;

  if (errors > 0) {
    showError(`${errors} 个来源采集时返回提示或错误；页面仍展示已获取结果。`);
  } else {
    clearError();
  }
}

function renderTopicStrip(sources) {
  const counts = new Map();
  for (const source of sources) {
    for (const paper of matchingPapersFor(source)) {
      const topics = Array.isArray(paper.matched_topics) ? paper.matched_topics : [];
      for (const topic of topics) {
        counts.set(topic, (counts.get(topic) || 0) + 1);
      }
    }
  }

  els.topicStrip.innerHTML = state.topics
    .map((topic) => `<span class="topic-pill">${escapeHtml(topic)} ${counts.get(topic) || 0}</span>`)
    .join("");
}

function sourceBadgeHtml(source) {
  const typeText = source.source_type === "nber" ? "NBER" : "期刊";
  const typeClass = source.source_type === "nber" ? "badge badge-nber" : "badge";
  const category = source.category ? `<span class="badge badge-field">${escapeHtml(source.category)}</span>` : "";
  return `<span class="${typeClass}">${typeText}</span>${category}`;
}

function renderPaper(paper) {
  const topics = Array.isArray(paper.matched_topics) ? paper.matched_topics : [];
  const chips = topics
    .map((topic, index) => `<span class="chip chip-${index % 4}">${escapeHtml(topic)}</span>`)
    .join("");
  const authors = paper.authors ? `${escapeHtml(paper.authors)}` : "";
  const date = paper.date ? `${escapeHtml(paper.date)}` : "";
  const metaParts = [authors, date].filter(Boolean);
  const meta = metaParts.length ? `<div class="paper-meta">${metaParts.join(" · ")}</div>` : "";
  const titleZh = paper.title_zh ? `<p class="cn-title">中文标题：${escapeHtml(paper.title_zh)}</p>` : "";
  const abstractEn = paper.abstract_en
    ? `<p class="abstract"><strong>Abstract:</strong> ${escapeHtml(paper.abstract_en)}</p>`
    : "";
  const abstractZh = paper.abstract_zh
    ? `<p class="abstract"><strong>中文摘要：</strong>${escapeHtml(paper.abstract_zh)}</p>`
    : "";

  return `
    <article class="paper-item">
      <h3 class="paper-title"><a href="${escapeHtml(paper.url || "#")}" target="_blank" rel="noopener">${escapeHtml(paper.title_en || "Untitled")}</a></h3>
      ${meta}
      <div class="chip-row">${chips}</div>
      ${titleZh}
      ${abstractEn}
      ${abstractZh}
    </article>
  `;
}

function renderSources() {
  const sources = filteredSources();
  renderSummary(sources);
  renderTopicStrip(sources);

  const cards = [];
  for (const source of sources) {
    const papers = matchingPapersFor(source);
    const total = Number(source.total_in_issue || source.total_recent_considered || 0);
    const paperHtml = papers.length
      ? papers.map(renderPaper).join("")
      : `<p class="empty-note">当前筛选条件下没有命中论文。</p>`;
    const issueUrl = source.issue_url || source.url || "#";
    const issueTitle = source.issue_title || "Latest issue";
    const errorHtml = source.error ? `<div class="source-error">提示：${escapeHtml(source.error)}</div>` : "";

    cards.push(`
      <section class="source-card">
        <div class="source-header">
          <div class="source-title-row">
            <h2 class="source-title">${escapeHtml(source.name || "")}</h2>
            <div class="source-badges">${sourceBadgeHtml(source)}</div>
          </div>
          <div class="source-meta">
            <a href="${escapeHtml(issueUrl)}" target="_blank" rel="noopener">${escapeHtml(issueTitle)}</a>
            · 命中 ${papers.length} / ${Number(source.matched_count || 0)}
            · 扫描 ${total}
          </div>
          ${errorHtml}
        </div>
        <div class="paper-list">${paperHtml}</div>
      </section>
    `);
  }

  els.sourceList.innerHTML = cards.length ? cards.join("") : `<p class="empty-note">没有匹配的来源。</p>`;
}

function showError(message) {
  els.errorBox.hidden = false;
  els.errorBox.textContent = message;
}

function clearError() {
  els.errorBox.hidden = true;
  els.errorBox.textContent = "";
}

async function loadData(showLoadingText = true) {
  if (window.location.protocol === "file:") {
    els.updateTime.textContent = "本地 file:// 模式";
    showError("请用 `python -m http.server 8000` 启动本地 HTTP 服务后访问页面。");
    return;
  }

  if (showLoadingText) {
    els.updateTime.textContent = "加载中...";
  }
  clearError();

  try {
    let response = null;
    let lastStatus = "";

    for (const path of DATA_PATHS) {
      const url = new URL(path, window.location.href).toString();
      const candidate = await fetch(`${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`, {
        cache: "no-store",
      });
      if (candidate.ok) {
        response = candidate;
        break;
      }
      lastStatus = `HTTP ${candidate.status} @ ${url}`;
    }

    if (!response) {
      throw new Error(lastStatus || "No reachable data URL.");
    }

    const payload = await response.json();
    const tracker = getTracker(payload);
    const sources = getSources(tracker);
    const topics = Array.isArray(tracker.topics) ? tracker.topics : [];
    const translation = payload.translation || {};

    state.payload = payload;
    state.tracker = tracker;
    state.sources = sources;
    state.topics = topics;

    fillFilterOptions();
    renderSources();

    const updatedAt = payload.updated_at ? `${payload.updated_at} UTC` : "未知";
    const translationStatus = translation.enabled
      ? `翻译已启用 success=${translation.success_count ?? "N/A"}, fail=${translation.fail_count ?? "N/A"}`
      : "翻译未启用";
    els.updateTime.textContent = `数据更新时间：${updatedAt} | ${translationStatus}`;
  } catch (error) {
    els.updateTime.textContent = "数据加载失败";
    showError(`无法加载数据：${error.message}`);
    els.summaryCards.innerHTML = "";
    els.topicStrip.innerHTML = "";
    els.sourceList.innerHTML = "";
  }
}

function bindEvents() {
  els.refreshBtn.addEventListener("click", () => loadData(false));
  els.topicFilter.addEventListener("change", renderSources);
  els.sourceTypeFilter.addEventListener("change", renderSources);
  els.sourceFilter.addEventListener("change", renderSources);
  els.searchInput.addEventListener("input", renderSources);
}

bindEvents();
loadData(true);
setInterval(() => loadData(false), 5 * 60 * 1000);

