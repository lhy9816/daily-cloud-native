# Daily Cloud Native Briefing - Design Spec

Date: 2026-03-27

## 1. Overview

A daily automated tool that collects, analyzes, and pushes high-signal cloud native updates to Feishu (Lark) group chat every morning at 08:00 (CST), and archives the digest as Markdown files to a GitHub repository. The tool covers CNCF ecosystem, cluster scheduling, AI inference, AI agents, and cluster compute enablement.

## 2. Architecture

### 2.1 Approach: Modular Python Scripts (Option A)

Each information source has an independent Collector plugin. Collectors run concurrently via asyncio, feed raw data into a centralized AI processing pipeline, then format and push to Feishu.

### 2.2 Data Flow

```
Windows Task Scheduler (08:00 daily)
        |
        v
    main.py (orchestrator)
        |
   +----+----+----+----+
   |    |    |    |    |    (asyncio concurrent)
   v    v    v    v    v
GitHub CNCF ArXiv Blogs WeChat   (collectors/)
   |    |    |    |    |
   +----+----+----+----+
        |
        v
   processor.py
   1. Dedup (URL + title similarity)
   2. LLM batch analysis (deep technical insight per source type)
   3. Score and rank, select Top N
        |
        v
   formatter.py
   (assemble Feishu Interactive Card)
        |
        v
   notifier.py
   (POST Feishu Webhook)
         |
         v
   archiver.py
   1. Render digest to Markdown
   2. git add + commit + push to GitHub
```

### 2.3 Error Isolation

- Each Collector runs in independent try/catch; single source failure does not block others
- Collector timeout: 60s per source
- Feishu push retry: 3 attempts with 10s interval
- All raw and processed data persisted to disk for debugging

## 3. Collectors

### 3.1 Unified Data Structure

```python
@dataclass
class RawItem:
    title: str
    url: str
    source_type: str       # "github" | "cncf" | "arxiv" | "blog" | "wechat"
    content: str           # raw content/abstract for LLM analysis
    published_at: str
    extra: dict            # source-specific fields (stars, authors, repo_name, etc.)
```

### 3.2 GitHub Collector (`collectors/github.py`)

**Data Source**: GitHub REST API / Search API (requires GITHUB_TOKEN)

**Strategy**:
- Search repos created/updated in last 24h with keywords: `kubernetes`, `cloud-native`, `llm-inference`, `ai-agent`, `gpu-scheduling`, `volcano`, `kserve`, `triton`, `vllm`, `karpenter`, `cluster-api`, `kube-bench`, `rancher`, `k3s`, `crossplane`, `argo`, `backstage`, `kyverno`, `open-telemetry`, `cilium`, `istio`, `envoy`
- Monitor 20-30 high-signal repos for recent releases: kubernetes/kubernetes, cilium/cilium, istio/istio, envoyproxy/envoy, prometheus/prometheus, argoproj/argo-cd, volcano-sh/volcano, kserve/kserve, vllm-project/vllm, triton-inference-server/triton, langchain-ai/langchain, crewAIInc/crewAI, open-telemetry/opentelemetry, kyverno/kyverno, crossplane/crossplane, kubeflow/kubeflow, dapr/dapr, knative/serving
- Return: repo_name, description, url, stars, recent_activity, release_info

**Dedup**: URL-level dedup + cross-day dedup (read previous day's data file)

### 3.3 CNCF/K8s Collector (`collectors/cncf.py`)

**Data Source**:
- CNCF Blog RSS: `https://www.cncf.io/feed/`
- Kubernetes Blog RSS: `https://kubernetes.io/blog/feed.xml`
- CNCF project page updates (via project list API)
- CNCF incubating/graduating project GitHub releases (dedup with GitHub Collector)

**Strategy**: RSS parsing + filter last 24h entries

### 3.4 ArXiv Collector (`collectors/arxiv.py`)

**Data Source**: arXiv API (`http://export.arxiv.org/api/query`)

**Strategy**:
- Search categories: `cs.DC` (Distributed Computing), `cs.SE` (Software Engineering), `cs.LG` (Machine Learning - infra related)
- Keyword filter: `kubernetes`, `container`, `cloud-native`, `scheduling`, `inference`, `LLM serving`, `GPU`, `cluster`, `MLOps`, `AI agent`, `operator`, `service mesh`, `observability`, `ebpf`, `serverless`
- Retrieve last 24h papers, max 30 candidates
- Download abstract for LLM analysis

### 3.5 Tech Blogs Collector (`collectors/blogs.py`)

**Data Source** (RSS-available):
- InfoQ Cloud Native RSS
- The New Stack RSS
- AWS/Google/Azure engineering blog RSS feeds
- High-signal individual blogs (Kelsey Hightower, Tim Hockin, etc.)

**Strategy**: Unified RSS parsing + keyword filtering

### 3.6 WeChat Collector (`collectors/wechat.py`)

**Data Source**: RSSHub WeChat route (requires self-hosted RSSHub + WeChat plugin)

**Target accounts**:
- WeChat official accounts: cloud-native-lab, KubeSphere, DaoCloud, Alibaba Cloud Native, Tencent Cloud Native, Huawei Cloud Native, ServiceMesher

**Fallback**: If RSSHub WeChat route is unstable, use WeRSS or similar third-party service as RSS source

**Strategy**: RSS parsing + filter last 24h articles

## 4. AI Processing Pipeline

### 4.1 Source-Type-Specific Deep Analysis

The LLM does NOT produce simple summaries. Instead, it performs differentiated deep technical analysis based on source type.

**Paper (arxiv/academic)**:
```
- Core problem: what problem does it solve
- Key architecture: overall system/method design approach
- Key techniques: core innovations, tricks, design choices
- Experimental results: key data, benchmark comparisons, improvement margins
- Contribution summary: one-line core contribution
- Recommendation: must-read / recommended / optional
```

**Blog / Engineering Article**:
```
- Core topic: what technology does it cover
- Technical points: key concepts, principles, design thinking (accessible language)
- Practical value: what can be learned, how to apply
- Impact analysis: implications for industry / technology direction
- Recommendation: must-read / recommended / optional
```

**GitHub Project**:
```
- Project positioning: what it does
- Technical highlights: why it's noteworthy, unique technical features
- Community momentum: stars, recent activity
- Usability: can it be used directly, applicable scenarios
- Recommendation: must-read / recommended / optional
```

**WeChat Article**: Same as Blog/Engineering Article format.

### 4.2 Prompt Strategy

- Each source type uses a dedicated System Prompt embedding the required analysis dimensions
- Output limited to 150-250 characters (Chinese) per item, balancing depth with Feishu card readability
- Batch processing: 5-8 items per batch to avoid context length degradation
- Prompt templates stored in `prompts/` directory as separate .md files

### 4.3 Scoring and Ranking

- Each analyzed item receives a numeric score (1-10) based on: recency, source credibility, ecosystem relevance, downstream impact, actionability
- Top line summary generated by a separate LLM call over the full day's analyzed items
- Each category section shows Top 3 items by score
- Total message capped at 20-30 items via score threshold

### 4.4 Model and Cost

- Default model: `gpt-4o-mini` or `deepseek-chat` (low cost, sufficient quality)
- Higher quality option: `gpt-4o` or `glm-4` (switchable via config)
- Provider and model configurable in `config.yaml`, no hardcoding

**Token estimate per run**:

| Step | Input tokens | Output tokens |
|------|-------------|---------------|
| Raw data from all collectors | ~15,000 | - |
| LLM deep analysis (20-30 items) | ~20,000 | ~6,000 |
| Top line generation | ~5,000 | ~300 |
| **Total** | **~40,000** | **~6,300** |

**Cost estimate**: `gpt-4o-mini` ~$0.03/run (~$1/month); `deepseek-chat` ~0.1 CNY/run (~3 CNY/month)

## 5. Feishu Message Format

### 5.1 Interactive Card Structure

```
+-------------------------------------+
|  Daily Cloud Native Briefing 2026-03-27 |
|  ------------------------------------ |
|  [Top Line] Today's 2-3 most important items |
+-------------------------------------+
|  Papers                              |
|  ------------------------------------ |
|  [Title] (link)                      |
|  Core problem: ...                   |
|  Key architecture: ...               |
|  Key techniques: ...                 |
|  Experimental results: ...           |
|  Contribution: ...                   |
|  Recommendation: must-read           |
+-------------------------------------+
|  GitHub                              |
|  ------------------------------------ |
|  [Project] 1.2k stars (link)         |
|  Technical highlights: ...           |
|  Usability: ...                      |
|  Recommendation: recommended         |
+-------------------------------------+
|  CNCF / K8s                          |
|  ...                                 |
+-------------------------------------+
|  Tech Blogs                          |
|  ...                                 |
+-------------------------------------+
|  WeChat Official Accounts            |
|  ...                                 |
+-------------------------------------+
|  Today's Recommendations             |
|  1. [Must-read item 1]               |
|  2. [Must-read item 2]               |
|  3. [Must-read item 3]               |
|  Monitor: ...                        |
|  Optional: ...                       |
+-------------------------------------+
```

### 5.2 Section Rules

- Each category section: max 3 items (ranked by LLM score)
- Sections with fewer than 2 items may be merged or omitted
- Total items in message: 20-30, auto-trimmed by score threshold
- Feishu Interactive Card format with rich text support

### 5.3 Push Failure Handling

- Retry 3 times with 10s interval on Webhook failure
- After 3 failures: write to `data/errors/YYYY-MM-DD.log`
- Data files are still saved for manual review

### 5.4 GitHub Archiver (`archiver.py`)

**Trigger**: Runs after successful Feishu push.

**Functionality**:
- Renders the day's digest as a Markdown file identical in content to the Feishu card (Top line, category sections, recommendation list)
- Writes to `content/YYYY-MM-DD.md`
- Executes `git add content/YYYY-MM-DD.md && git commit -m "daily: YYYY-MM-DD cloud native briefing" && git push origin main`
- Repository path, content directory, remote, and branch configurable in `config.yaml` under `github_archive`

**Error Handling**:
- Git operation failures written to `data/errors/YYYY-MM-DD.log`
- Does not affect Feishu push or data file persistence

## 6. Scheduling and Deployment

### 6.1 Windows Task Scheduler

```
Trigger: Daily at 08:00 CST
Action: python D:\lihangyu\2026\2026Q1\cloud-native-daily\main.py
```

- Use `pythonw.exe` for silent execution, or redirect output to log file
- 10-minute timeout, auto-terminate on exceed

### 6.2 Configuration (`config.yaml`)

```yaml
sources:
  github:
    token: "${GITHUB_TOKEN}"
    keywords: [kubernetes, cloud-native, llm-inference, ai-agent, gpu-scheduling, ...]
    watch_repos: [kubernetes/kubernetes, cilium/cilium, istio/istio, ...]
  arxiv:
    categories: [cs.DC, cs.SE, cs.LG]
    keywords: [kubernetes, container, cloud-native, scheduling, inference, ...]
  cncf:
    feeds:
      - "https://www.cncf.io/feed/"
      - "https://kubernetes.io/blog/feed.xml"
  blogs:
    feeds: [InfoQ, TheNewStack, AWS Blog, GCP Blog, Azure Blog, ...]
  wechat:
    rsshub_url: "http://localhost:1200"
    accounts: [cloud-native-lab, KubeSphere, DaoCloud, aliyun-cloudnative, ...]

llm:
  provider: "openai"
  model: "gpt-4o-mini"
  api_key: "${LLM_API_KEY}"
  base_url: ""                # optional, custom endpoint
  batch_size: 6

feishu:
  webhook_url: "${FEISHU_WEBHOOK_URL}"

github_archive:
  repo_path: "."              # local repo path
  content_dir: "content"
  remote: "origin"
  branch: "main"

schedule:
  timezone: "Asia/Shanghai"
  time: "08:00"
  timeout_minutes: 10
```

Sensitive values injected via environment variables (`.env` file), never committed to config.

### 6.3 Project Directory Structure

```
daily-cloud-native/
+-- main.py                   # Entry point + orchestrator
+-- config.yaml               # Configuration
+-- .env                      # Secrets (not committed)
+-- requirements.txt
+-- collectors/
|   +-- __init__.py
|   +-- base.py               # BaseCollector abstract class
|   +-- github.py
|   +-- cncf.py
|   +-- arxiv.py
|   +-- blogs.py
|   +-- wechat.py
+-- processor.py              # LLM deep analysis pipeline
+-- formatter.py              # Feishu card assembly
+-- notifier.py               # Feishu Webhook push
+-- archiver.py               # GitHub Markdown archive + git push
+-- models.py                 # Data structure definitions
+-- prompts/                  # LLM prompt templates
|   +-- paper_prompt.md
|   +-- github_prompt.md
|   +-- blog_prompt.md
|   +-- wechat_prompt.md
|   +-- summary_prompt.md     # Top line generation
+-- data/                     # Runtime data (gitignored)
|   +-- 2026-03-27.json
|   +-- errors/
+-- content/                  # GitHub archive Markdown (git tracked)
|   +-- .gitkeep
+-- logs/
+-- tests/
    +-- test_collectors.py
    +-- test_processor.py
    +-- test_formatter.py
```

### 6.4 Logging

- Logs written to `logs/YYYY-MM-DD.log`
- Each step records: timestamp, duration, status, item count
- Raw collected data and processed data stored separately in `data/`

## 7. Topic Coverage

The tool focuses on these cloud native directions:

- **CNCF ecosystem**: Kubernetes core, CNI/CSI/CRI, Gateway API, project graduations
- **Cluster scheduling**: Volcano, Karpenter, YuniKorn, cluster autoscaling, batch scheduling
- **AI inference on K8s**: KServe, Triton, vLLM, model serving, GPU scheduling, inference optimization
- **AI agents**: agent frameworks on K8s, LangChain, CrewAI, multi-agent orchestration
- **Cluster compute enablement**: GPU sharing, MIG, RDMA, SPDK, heterogeneous computing
- **Platform engineering**: Crossplane, Backstage, ArgoCD, GitOps, developer platforms
- **Observability**: OpenTelemetry, Prometheus, Grafana, eBPF
- **Service mesh**: Istio, Cilium, Envoy, Gateway API
- **Security**: Kyverno, OPA/Gatekeeper, supply chain security

## 8. Dependencies

- Python 3.10+
- `httpx` or `aiohttp` (async HTTP client)
- `feedparser` (RSS parsing)
- `openai` or `zhipuai` (LLM client)
- `pyyaml` (config)
- `python-dotenv` (env vars)
- `pydantic` (data models)
- `lxml` (XML parsing for arXiv)

## 9. Out of Scope (v1)

- RSSHub deployment (assumed pre-existing or separately managed)
- Feishu bot application approval flow
- Web UI for managing sources or viewing history
- Multi-language digest (Chinese only for v1)
- User feedback loop or click tracking
