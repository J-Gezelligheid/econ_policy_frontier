# Econ Policy Frontier Tracker

独立网页仓库，用于追踪经济学顶刊、相关 field top 期刊和 NBER Working Papers 中与下列主题相关的最新研究：

- 产业政策
- 创新
- 绿色发展
- 人工智能

网页入口：`index.html`

## 数据来源

- 经济学顶刊和 field top 期刊：通过 Crossref 最新期目录抓取，再用 OpenAlex 补充部分摘要。
- NBER Working Papers：通过 NBER 官方公开 metadata TSV 抓取最近工作论文。
- 中文标题/摘要：可选使用 Kimi API 翻译，配置 `KIMI_API_KEY` 后启用。

## 结构

```text
.
├── index.html
├── assets/
│   ├── css/site.css
│   └── js/app.js
├── data/
│   └── policy_frontier.json
├── scripts/
│   └── update_policy_frontier.py
├── .github/workflows/update_policy_frontier.yml
└── requirements.txt
```

## 本地更新

```powershell
python -m pip install -r requirements.txt
python scripts\update_policy_frontier.py
```

可选环境变量：

- `KIMI_API_KEY`
- `KIMI_MODEL`，默认 `moonshot-v1-8k`
- `MAX_POLICY_FRONTIER_PAPERS_PER_SOURCE`，默认 `12`
- `MAX_NBER_RECENT_PAPERS`，默认 `220`
- `POLICY_FRONTIER_TIMEOUT_SECONDS`，默认 `25`
- `ENABLE_OPENALEX_ABSTRACT_LOOKUP`，默认 `0`；设为 `1` 时会为缺失摘要的期刊论文逐篇补抓 OpenAlex，更新会明显变慢。
- `LOAD_NBER_PROGRAMS`，默认 `0`；设为 `1` 时额外读取 NBER program metadata。
- `TRACKER_CONTACT_EMAIL`，Crossref polite pool User-Agent 邮箱。

## 本地预览

请用 HTTP 服务预览，不要直接双击 HTML：

```powershell
python -m http.server 8000
```

然后打开：

```text
http://localhost:8000/
```

## GitHub Pages

推到 GitHub 后，在仓库 Settings -> Pages 中选择从 `main` 分支根目录发布。定时更新工作流会每周运行一次，也可在 Actions 页面手动触发。

如果需要中文翻译，请在仓库 Secrets 添加：

- `KIMI_API_KEY`
