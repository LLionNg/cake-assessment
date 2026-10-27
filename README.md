# TikTok KOL Matcher - Thailand

Prototype for the Convert Cake AI Engineer assessment. Give it a client's Facebook page
(and optionally their website) and it returns a ranked list of Thai TikTok creators, with
profile links, engagement metrics and a short reason for each match.

It runs fully offline in mock mode until API keys are added to `config.yml`, and mock mode
can be forced at any time with `mock.enabled: true`.

## Project structure

```
convert-cake/
  app.py                   launcher: uv run app.py starts the Streamlit UI
  config.example.yml       settings template without credentials, copy to config.yml
  config.yml               your settings and API keys, ignored by git (no .env)
  pyproject.toml, uv.lock  dependencies and the kol-match CLI entry point
  Dockerfile, docker-compose.yml
  fixtures/                mock Facebook page and TikTok creators (JSON)
  src/                     the application package, imported as src.*
    cli.py                 Typer CLI
    core/
      config.py            settings loaded from config.yml
      container.py         picks the LLM model and the data sources from config
    models/                LLM layer
      base.py              LLM interface and LLMError
      agent.py             OpenAI, Anthropic and Gemini on Vertex AI via Pydantic AI
      mock.py              keyword heuristics standing in for the LLM
    prompts/
      prompts.py           system prompts for brand profiling and creator assessment
    data/                  data layer
      base.py              FacebookSource and TikTokSource interfaces
      schemas.py           pydantic models shared across the app
      apify.py             Apify actor runner with disk cache
      mock.py              fixture-backed Facebook and TikTok data
      website.py           website text extraction (httpx + trafilatura)
    scrapers/              built-in scraper, a free alternative to Apify
      browser.py           headless Chromium session (Playwright)
      facebook.py          public Facebook pages and posts
      tiktok.py            TikTok discover pages, profile embeds, videos
    services/              business logic
      matcher.py           KOLMatcher orchestrating the steps
      profiler.py          brand profile and TikTok search terms
      discovery.py         candidate search, shortlist, enrichment, Thai filter
      assessor.py          LLM relevance and audience fit, batched in parallel
      scoring.py           metrics and weighted score
    ui/
      streamlit_app.py     Streamlit UI
    utils/                 small helpers shared across modules
      text.py              Thai script detection, keyword helpers
      urls.py              URL parsing and redirect checks
      log.py               logging setup from config.yml
  tests/
    test_models.py         LLM models, settings, thread safety, timeout guard
    test_matcher.py        end-to-end mock run and service selection
    test_scoring.py        tiers, engagement, Thai signal, score weights
    test_scrapers.py       URL parsing and data mapping for the scrapers
```

1. **Brand profiling** - the Facebook page (intro, about, categories, followers) and the
   website text are sent to the LLM, which returns a typed `BrandProfile`: industry,
   products, target audience, content style, Thai and English TikTok search queries,
   hashtags, and the creator tiers that suit the brand size.
2. **Discovery** - the queries and hashtags are searched on TikTok by one of two sources:
   - **Apify** (`apify.api_token`): the TikTok scraper actor searches videos through a
     Thai proxy, then fetches every shortlisted creator's latest videos in one more run.
   - **Built-in scraper** (`scraper.enabled: true`): headless Chromium opens TikTok's
     public `/discover/<keyword>` page for each term, then each shortlisted creator's
     profile embed for their recent videos. Free, but slower.

   Either way, videos are grouped by author, filtered by follower range and shortlisted
   by reach before the profile step. Creators without enough Thai signal (Thai script in
   bio or captions, or `TH` upload location) are then dropped.
3. **Assessment** - creators are sent to the LLM in batches (in parallel) and scored for
   content relevance and estimated audience fit, with a one or two sentence reason.
4. **Scoring** - a transparent weighted score:

| Signal       | Weight | Source                                                       |
|--------------|--------|--------------------------------------------------------------|
| relevance    | 0.40   | LLM, content niche and style vs brand                        |
| audience_fit | 0.25   | LLM estimate from content signals                            |
| engagement   | 0.25   | median (likes + comments + shares) / views, vs 8% benchmark  |
| tier_fit     | 0.10   | follower tier in the brand's preferred tiers                 |

Creator tiers by follower count, tier 1 being the highest reach:

| Tier | Followers   |
|------|-------------|
| 1    | 1M+         |
| 2    | 500k - 1M   |
| 3    | 100k - 500k |
| 4    | 10k - 100k  |
| 5    | under 10k   |

Weights, filters and limits are all set in `config.yml`.

## Quick start

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/), or Docker.

```bash
cp config.example.yml config.yml
uv sync
uv run app.py
```

`config.yml` holds your keys and is ignored by git. `config.example.yml` is the committed
template with every credential left empty, so a fresh copy runs in mock mode.

Extra Streamlit flags pass through, for example `uv run app.py --server.port 8502`.

For the built-in scraper (`scraper.enabled: true`), install its browser once:

```bash
uv run playwright install chromium
```

CLI:

```bash
uv run kol-match --facebook https://www.facebook.com/somebrand --website https://somebrand.co.th --top 10 --output report.json
```

Docker:

```bash
docker compose up --build
```

Then open http://localhost:8501. The CLI also works in the container:

```bash
docker compose run --rm app kol-match --facebook https://www.facebook.com/somebrand
```

Tests:

```bash
uv run pytest
```

## Configuration

Everything lives in `config.yml`, created from `config.example.yml`. There is no `.env`
file. Docker mounts `config.yml` read-only, so edits apply after a container restart. The
image itself only contains the credential-free example, and `config.yml` is excluded from
the Docker build context.

| Key                | Purpose                                                     |
|--------------------|-------------------------------------------------------------|
| `log_level`        | `DEBUG`, `INFO`, `WARNING` or `ERROR` for this app's logs   |
| `llm.provider`     | `openai`, `anthropic` or `google-vertex`                    |
| `llm.effort`       | Reasoning effort `low`, `medium`, `high`, empty for default |
| `llm.<provider>.*` | Credentials and model for each provider, see below          |
| `apify.api_token`  | Apify token. Empty means mock Facebook and TikTok data      |
| `apify.max_charge_usd` | Spend cap per actor run                                 |
| `apify.cache_dir`  | Scraped datasets are cached here to avoid paying twice      |
| `scraper.enabled`  | `true` reads Facebook and TikTok with the built-in scraper  |
| `scraper.delay_s`  | Pause between page loads                                    |
| `mock.enabled`     | `true` forces mock for every service, even with keys set    |
| `mock.facebook_page`, `mock.tiktok_creators` | Fixture files used by the mock providers |
| `matching.*`       | Candidate limits, follower range, Thai ratio, weights       |

With `mock.enabled: false`, each service picks live or mock on its own: a service with a
key runs live, a service with an empty key falls back to mock. Facebook and TikTok data
comes from the built-in scraper when `scraper.enabled` is true, otherwise Apify when it
has a token, otherwise mock. So you can mix, for example live scraped data with the
mock LLM. The current mode is shown in the UI and
CLI output.

### Matching settings

| Key                    | Default | Meaning                                                                 |
|------------------------|---------|-------------------------------------------------------------------------|
| `search_queries`       | 10      | TikTok search phrases the LLM writes per run, spread over six angles. Extra ones are dropped. |
| `hashtags`             | 10      | TikTok hashtags the LLM writes per run. Each query and hashtag is one TikTok search. |
| `min_thai_ratio`       | 0.3     | Minimum share of a creator's bio and videos with Thai script or a `TH` upload location. Creators below it are dropped as not Thai. |
| `engagement_benchmark` | 0.08    | Engagement rate that earns a full engagement score. A creator at 4% scores 0.5; 8% or more scores 1.0. |
| `assess_batch_size`    | 10      | Creators sent to the LLM per assessment call. Batches run in parallel, up to 4 at a time. |
| `weights.relevance`    | 0.4     | Weight of the LLM's content fit score (0 to 1).                          |
| `weights.audience_fit` | 0.25    | Weight of the LLM's estimated audience match (0 to 1).                   |
| `weights.engagement`   | 0.25    | Weight of the engagement score above.                                    |
| `weights.tier_fit`     | 0.1     | Weight of tier fit: 1.0 if the creator's tier is one the brand prefers, otherwise 0.3. |

The final score is the weighted average of the four parts, divided by the sum of the
weights, so it stays between 0 and 1 even if the weights don't add up to 1:

```math
\text{score} = \frac{\sum_{i} \omega_i \, s_i}{\sum_{i} \omega_i}
= \frac{\omega_R R + \omega_A A + \omega_E E + \omega_T T}{\omega_R + \omega_A + \omega_E + \omega_T}
```

where $\omega$ are the `weights` and each part $s_i$ is between 0 and 1:

```math
\begin{aligned}
R &= \text{relevance, from the LLM} \\
A &= \text{audience fit, from the LLM} \\
E &= \min\left(\frac{\tilde{\epsilon}}{\epsilon_{\text{bench}}},\ 1\right) \\
\tilde{\epsilon} &= \mathrm{median}_{v} \left( \frac{\text{likes}_v + \text{comments}_v + \text{shares}_v}{\text{views}_v} \right) \\
T &= \begin{cases} 1.0 & \text{if the brand prefers the creator's tier} \\ 0.3 & \text{otherwise} \end{cases}
\end{aligned}
```

Here $\tilde{\epsilon}$ is the median engagement rate over the creator's videos $v$, and
$\epsilon_{\text{bench}}$ is `engagement_benchmark`.

### LLM providers

The LLM handles brand profiling and creator assessment. It runs through
[Pydantic AI](https://ai.pydantic.dev), so switching provider is a config change:

1. Set `llm.provider` to `openai`, `anthropic` or `google-vertex`.
2. Fill in the credentials in that provider's section under `llm`. The other sections can
   stay empty.

If the chosen provider has no credentials, the app falls back to the mock LLM.

| Provider        | What to fill in                                   | Where to get it                       |
|-----------------|---------------------------------------------------|---------------------------------------|
| `openai`        | `llm.openai.api_key` (`sk-...`)                   | platform.openai.com, API keys         |
| `anthropic`     | `llm.anthropic.api_key` (`sk-ant-...`)            | console.anthropic.com, API keys       |
| `google-vertex` | `llm.google_vertex.credentials_file`, a path to a service account JSON | Google Cloud console, IAM, Service accounts, Keys |

For Vertex AI, put the JSON in `credentials/` (ignored by git, mounted read-only in
Docker) and set `credentials_file: credentials/vertex.json`. `project_id` is read from
the file when left empty. The service account needs the Vertex AI User role, and
`location` must be a region where the model is available.

```yaml
llm:
  provider: google-vertex
  google_vertex:
    credentials_file: credentials/vertex.json
    location: global
    model: gemini-2.5-flash-lite
```

### Cost per run

The defaults keep one live match at about $0.40 on Apify, so the free plan's $5 monthly
credit covers around 12 runs:

| Step                | Results                                      | Price (Apify, 2026-10)      |
|---------------------|----------------------------------------------|-----------------------------|
| Facebook page       | 1 page                                       | $0.012 per page (free plan) |
| TikTok search       | 10 queries + 10 hashtags x 5 videos          | from $1.70 per 1,000        |
| TikTok profiles     | 15 creators x 4 videos                       | from $1.70 per 1,000        |

That is about 160 TikTok results, or $0.28 to $0.62 depending on the plan rate. The
"from" price is the lowest tier, and the free plan rate is higher. Repeat runs with the
same input are free thanks to the cache. Raise `matching.videos_per_query`,
`max_candidates` and `videos_per_creator` for a wider search at a higher cost.
LLM usage is billed separately by the chosen provider.

### Built-in scraper

A free alternative to Apify in `src/scrapers/`. It drives headless Chromium with
Playwright, logged out, and reads the JSON the sites already send to every visitor
instead of brittle CSS selectors.

| Source        | Accepted links                                              | What it reads                                  |
|---------------|-------------------------------------------------------------|------------------------------------------------|
| Facebook page | `/name`, `m.` / `web.` hosts, `/about`, `profile.php?id=`, `/pages/...`, `/people/...` | name, intro, about, category, exact followers, website |
| Facebook post | `/name/posts/...`, `permalink.php`, `/reel/`, `/share/`, `fb.me` | post text, plus the page that posted it        |
| TikTok search | brand queries and hashtags                                  | public `/discover/<keyword>` pages, full video stats and creator stats |
| TikTok creator | `@name`, `tiktok.com/@name/...`, `vt.` / `vm.` short links | profile embed: bio, followers, likes, last videos |
| TikTok video  | any video link                                              | full stats for that video                      |

Trade-offs against Apify:

- A run takes 3 to 6 minutes. TikTok rate limits profile embeds, and the scraper backs off
  and retries instead of pushing through. A creator whose embed still fails keeps the data
  found during search.
- Profile embeds show views but not likes, so engagement uses only the videos found in
  search, which have full stats.
- Discover pages exist only for keywords TikTok has indexed. A query with no page adds
  nothing.

## Mock mode

With `mock.enabled: true`, or when a key is empty, the app uses
`src/models/mock.py` and `src/data/mock.py`:

```yaml
mock:
  enabled: true
  facebook_page: fixtures/facebook_page.json
  tiktok_creators: fixtures/tiktok_creators.json
```

## Key technical decisions

- **Apify instead of the official TikTok API.** TikTok's Research API is closed to
  commercial users and to Thailand, and the Creator Marketplace API is partner only.
  Apify's TikTok scraper returns public profile and video metrics with a Thai proxy.
- **Pydantic AI for the LLM layer.** One agent API over OpenAI, Anthropic and Gemini on
  Vertex AI, with typed pydantic outputs, output validation retries and token usage per
  call. Switching provider is a config change. Pydantic AI is async, so `models/agent.py`
  runs one background event loop and the rest of the app stays synchronous.
- **LLM for understanding, code for numbers.** The LLM handles what needs language
  understanding (brand profile, content fit, Thai and English keywords). Engagement,
  tiers and the final score are deterministic and unit tested, so the ranking can be
  explained and tuned.
- **Structured outputs.** Every LLM call returns a validated pydantic model, so there
  is no free-text parsing.
- **Cost control.** Two actor runs per match (search, then one batched profile run), a
  spend cap per run, and a disk cache keyed by actor input. System prompts are cached
  (Anthropic needs an explicit marker; OpenAI and Gemini cache repeated prefixes
  automatically), and every call logs its cache read and write tokens.
- **Small interfaces.** The LLM and each data source sit behind a small abstract class, so
  mock and live versions swap by config and a new source (for example the TikTok
  Creator Marketplace) can be added without touching the pipeline.

## Ethics and privacy

- Only public data is used: public Facebook pages and public TikTok profiles and videos.
  No logins, private data or personal profiles.
- Audience demographics are not available publicly. `audience_fit` is an estimate from
  content signals and is labelled as such. The prompt tells the model not to infer
  sensitive traits.
- Scraped data is cached locally only to reduce cost. Delete `.cache/` to clear it. A
  production version should set a retention period in line with Thailand's PDPA.
- Every recommendation comes with a reason, and the final call stays with the
  influencer team. The tool shortlists; it does not decide.
- Scraping must respect platform terms. The built-in scraper only opens public pages that
  any logged-out visitor sees. It uses no accounts, solves no CAPTCHAs, bypasses no blocks
  and slows down when a site rate limits it. Both platforms restrict automated
  collection, so it is off by default and meant for demos. Production should use Apify's
  managed actors or official partner APIs.

## Limitations

- Real audience demographics (age, gender, location) need first-party data such as
  TikTok Creator Marketplace or a creator's own analytics export.
- Discovery depends on the generated keywords and hashtags. Niche brands may need manual
  query tweaks.
- Follower and view counts can be inflated by fake engagement. There is no fraud check yet.

## Future enhancements

- Comment language and sentiment analysis to estimate audience more accurately.
- Brand safety screening of recent videos.
- Embedding-based pre-ranking for larger candidate pools.
- Campaign feedback loop: learn weights from which KOLs the team actually books and how
  their campaigns perform.
- Price estimation per tier and CRM export.

## Citations

- Apify TikTok Scraper: https://apify.com/clockworks/tiktok-scraper
- Apify Facebook Pages Scraper: https://apify.com/apify/facebook-pages-scraper
- TikTok Research API eligibility FAQ: https://developers.tiktok.com/docs/en/research-api-faq
- TikTok Creator Marketplace API announcement: https://techcrunch.com/2021/08/31/tiktoks-new-creator-marketplace-api-lets-influencer-marketing-companies-tap-into-first-party-data
- Pydantic AI: https://ai.pydantic.dev
- Vertex AI service account authentication: https://cloud.google.com/iam/docs/service-account-creds
- trafilatura: https://trafilatura.readthedocs.io
- Playwright for Python: https://playwright.dev/python/
- uv: https://docs.astral.sh/uv/
- Thailand Personal Data Protection Act (PDPA) B.E. 2562 (2019)
