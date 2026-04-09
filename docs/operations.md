# Slug-Ig-Crawler — reference

This document is part of the [Slug-Ig-Crawler](../README.md) documentation. Paths are relative to the repository root unless noted.

# Docker and Docker Compose

The scraper supports running in Docker containers, providing a consistent environment across different platforms and simplifying deployment.

### Docker Support

Docker support is controlled via the `use_docker` configuration option in `config.toml`:

```toml
[main]
use_docker = true  # Set to true when running in Docker
```

When `use_docker=True`, the backend:
- Uses `CHROME_BIN` / `CHROMEDRIVER_BIN` when set; otherwise the same pinned paths as the `Dockerfile` (`/opt/chrome-linux64/chrome`, `/opt/chromedriver-linux64/chromedriver`)
- Applies Docker-specific Chrome flags: `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`
- Uses `/tmp/chrome-profile` as the Chrome user data directory (can be overridden via `IGSCRAPER_CHROME_PROFILE` env var)
- Configures platform identity as "Linux x86_64"

### Dockerfile

The project includes a `Dockerfile` that:
- Uses Python 3.10 slim base image
- Installs Chrome for Testing (version-locked to 143.0.7499.170) and matching ChromeDriver
- Installs all Python dependencies from `requirements.txt`
- Sets up environment variables for Chrome binaries
- Includes version validation to ensure Chrome and ChromeDriver major versions match

**Key Dockerfile Features:**
- Version-locked Chrome installation for reproducibility
- Hard assertion that Chrome and ChromeDriver major versions match
- Proper Chrome runtime dependencies installed
- Optimized for Linux x86_64 platform

### Docker Compose

The repository includes a **canonical** `docker-compose.yml` (service name **`Slug-Ig-Crawler`**, image built from this `Dockerfile`) for local and manual runs. **Thor and other orchestrators do not ship this file**; they use whatever path is in **`DOCKER_COMPOSE_FILE`** and typically run one-off jobs like:

```bash
docker compose -f /path/to/compose.yml run --rm -v "$WORKSPACE:/job" Slug-Ig-Crawler \
  Slug-Ig-Crawler --config /job/config.toml
```

The compose file in this repo sets `PYTHONPATH`, `CHROME_BIN`, `CHROMEDRIVER_BIN`, and `shm_size: 2gb` to match the image. Optional host-specific variables (GCS credentials, etc.) can be passed with `-e` or via a local `.env` (see `.env.example`; use e.g. `docker compose --env-file .env …` if you add one).

**Usage (examples):**

```bash
docker compose build
docker compose run --rm Slug-Ig-Crawler Slug-Ig-Crawler --config config.toml
```

**Prerequisites:**
- Docker and Docker Compose installed
- Valid `config.toml` with `use_docker = true` for in-container runs
- For GCS upload from the container, mount credentials and set `GOOGLE_APPLICATION_CREDENTIALS` as appropriate

**Important Notes:**
- The Chrome profile directory defaults to `/tmp/chrome-profile` (RAM-mounted on remote servers) and is automatically created if it doesn't exist. Can be overridden via `IGSCRAPER_CHROME_PROFILE` environment variable.
- Shared memory size (`shm_size`) in compose is set to reduce Chrome crashes in containers

---

## Data Persistence

### Local Storage

Data is persisted to local files in JSONL (JSON Lines) format:

- **Metadata File**: Contains complete post data including title, media, likes, comments
- **Skipped File**: Logs posts that failed to scrape with error reasons
- **Post Entity File**: Parsed GraphQL entities (comments, replies) with flattened structure
- **Profile File**: Profile page GraphQL data

### Cloud Storage Integration

Completed data files are automatically:

1. **Sorted**: JSONL files are sorted by timestamp (optional)
2. **Uploaded**: Files are uploaded to Google Cloud Storage (GCS)
3. **Enqueued**: GCS URIs are enqueued to PostgreSQL database for downstream processing

### Screenshot Video Finalization

When `enable_screenshots = true` in configuration, the scraper automatically:

1. **Captures Screenshots**: Takes periodic screenshots (every 7 seconds) during scraping, saved as `.webp` files in `shot_dir`
2. **Generates Video**: At shutdown, converts all screenshots into a single MP4 video:
   - **FPS**: 2.5 frames per second
   - **Resolution**: 640p height (width auto-scaled to preserve aspect ratio)
   - **Format**: MP4 (H.264 codec)
   - **Location**: Generated in-place in the screenshot directory
3. **Uploads to GCS**: Video is uploaded to `gs://{bucket}/vid_log/{video_name}.mp4`
   - **PROFILE mode**: `profile_{consumer_id}_{profile_name}_{timestamp}.mp4`
   - **POST mode**: `post_{consumer_id}_{run_name}_{timestamp}.mp4`
   - **Bucket Name Validation**: The bucket name is automatically sanitized and validated:
     - Handles path-like bucket names (e.g., `/app/pugsy_ai_crawled_data` → `pugsy_ai_crawled_data`)
     - Removes `gs://` prefix if present
     - Validates GCS bucket name format (must start/end with letter/number, 3-63 chars)
     - Works correctly in both local and Docker environments
4. **Cleans Up**: After successful upload (or on failure), all local screenshots and the video file are deleted

**Requirements:**
- At least 2 screenshots must exist (otherwise video generation is skipped)
- `gcs_bucket_name` must be configured in `config.toml`
- Video finalization runs automatically during shutdown (no manual intervention needed)

**Configuration:**
- **Bucket Name**: Can be specified as:
  - Simple name: `gcs_bucket_name = "pugsy_ai_crawled_data"`
  - With `gs://` prefix: `gcs_bucket_name = "gs://pugsy_ai_crawled_data"` (prefix is automatically removed)
  - Path-like values are handled: If the config value looks like a path (e.g., `/app/pugsy_ai_crawled_data`), the basename is extracted automatically
- **Consumer ID**: Used in video filename for identification
- **Profile/Run Names**: Automatically sanitized to remove invalid filename characters

**Error Handling:**
- Video generation failures are logged but don't block shutdown
- GCS upload failures are logged but cleanup still runs
- Missing configuration fields result in skipped video generation (with warnings)
- Invalid bucket names are validated and sanitized automatically, with clear error messages if sanitization fails

### File Formats

**Metadata JSONL Format:**
```json
{
  "post_url": "https://www.instagram.com/p/ABC123/",
  "post_id": "post_0",
  "post_title": {
    "aHref": "/username/",
    "timeDatetime": "2024-01-01T12:00:00.000Z",
    "siblingTexts": ["Post caption text"]
  },
  "post_media": [...],
  "likes": {
    "likesNumber": 1000,
    "likesText": "1,000 likes"
  },
  "post_comments_gif": [...]
}
```

---

## Key Design Patterns

1. **Page Object Model**: Page interactions are encapsulated in `BasePage` and `ProfilePage` classes
2. **Backend Abstraction**: `Backend` abstract base class allows for different browser automation backends
3. **Configuration Management**: Pydantic models provide type-safe configuration with validation
4. **Registry Pattern**: GraphQL models are registered and matched dynamically
5. **Batch Processing**: Posts are processed in configurable batches to manage memory and rate limiting
6. **Error Handling**: Comprehensive try-except blocks with logging ensure graceful failure handling
7. **Resource Cleanup**: `finally` blocks ensure browser cleanup even on errors

---

## Dependencies

Key external dependencies:

- **selenium**: WebDriver automation
- **seleniumwire**: Network request interception
- **pydantic**: Configuration validation
- **google-cloud-storage**: GCS upload functionality
- **psycopg2**: PostgreSQL database connectivity
- **imageio** and **imageio-ffmpeg**: Video generation from screenshots
- **Pillow**: Image processing for screenshot resizing

---

## Security Considerations

1. **Platform policy and law**: Technical mitigations below do not replace compliance with Instagram / Meta terms or applicable law—see [Acceptable use and conflicts (README)](../README.md#acceptable-use-and-conflicts).
2. **URL Validation**: `chrome.py` patches WebDriver methods to monitor for suspicious navigation
3. **Cookie Security**: Cookies are stored locally and never exposed in logs
4. **Rate Limiting**: Random delays and batch processing reduce detection risk
5. **Anti-Detection**: Chrome options configured to evade bot detection

---

## Troubleshooting

### Common Issues

1. **ChromeDriver not found**: 
   - Set `CHROME_BIN` and `CHROMEDRIVER_BIN` to override in any mode; otherwise local runs use optional TOML paths or macOS defaults, Docker runs use the image’s pinned paths
2. **Version mismatch**: Chrome and ChromeDriver major versions must match. The Dockerfile validates this automatically.
3. **Cookie authentication fails**: Regenerate cookies using `login_Save_cookie.py`. In Docker, ensure cookies are in the mounted Chrome profile directory.
4. **Rate limiting**: Increase `rate_limit_seconds_min` and `rate_limit_seconds_max` in config
5. **Memory issues**: Reduce `batch_size` to process fewer posts simultaneously. In Docker, adjust `mem_limit` and `mem_reservation` in docker-compose.yml if needed.
6. **Docker-specific issues**: 
   - Ensure `use_docker=true` in config when running in Docker
   - Check that shared memory size is sufficient (default is 2GB)
   - Verify all required volumes are properly mounted

### Debugging

- Set `headless = false` to observe browser behavior
- Set `logging.level = "DEBUG"` for verbose logging
- Validate TOML (including `[trace].thor_worker_id`) against `config.example.toml` before long runs

---

## Performance Timing & Observability

The scraper emits structured timing logs for performance analysis, bottleneck detection, and cost modeling. These logs are designed to be Prometheus/Loki-friendly and provide insights into both active processing time and total wall-clock time.

### Timing Metrics

The scraper tracks two distinct timing metrics:

#### Total Time
Measures **end-to-end wall time** from when a unit of work becomes eligible for processing until it completes (success or error). This includes:
- Scrolling operations
- Clicking actions
- DOM waits
- Network waits
- Explicit rate-limit sleeps
- Retries and backoff delays

Total time reflects **real-world scraping latency** as experienced by the system.

#### Active Time
Measures **intentional work time** spent on actual scraping operations. This includes:
- Scrolling actions
- Clicking
- DOM extraction
- Media extraction
- GraphQL capture and parsing

Active time **excludes**:
- Explicit `sleep()` calls
- Idle polling loops
- Backoff delays

Active time answers: *"How expensive is this profile or post to scrape?"*

**Required Invariant:** `active_time_ms <= total_time_ms` (always enforced)

### Log Events

Two separate structured log events are emitted for each tracked operation:

1. **`pipeline_total_time`** - Total wall-clock time
2. **`pipeline_active_time`** - Active processing time

These events are **never combined** into a single log entry. Each event is emitted independently with the same schema.

### Log Schema

Both timing events use the following structured schema (emitted as JSON):

| Field            | Value                                           |
|------------------|-------------------------------------------------|
| `event`          | `pipeline_active_time` OR `pipeline_total_time` |
| `category`       | `creator_profile` OR `creator_content`          |
| `creator_handle` | Instagram profile handle                        |
| `content_id`     | Post/Reel ID or URL slug, or `null` for profile |
| `pipeline`       | Fixed value: `"Slug-Ig-Crawler"`                      |
| `duration_ms`    | Integer milliseconds                            |
| `status`         | `"success"` or `"error"`                        |
| `error_type`     | Exception class name or `null`                  |
| `consumer_id`    | Consumer ID from config (or `null` if not set) |
| `thor_worker_id` | Value from `[trace].thor_worker_id` in config |

### Timing Levels

#### Profile-Level Timing

**Location:** `pipeline.py` - `_scrape_single_profile()`

**Scope:** Wraps the entire profile scraping execution, including:
- Profile navigation
- Post URL collection
- Batch post scraping

**Category:** `creator_profile`

**Example Log Entries:**
```json
{"event": "pipeline_total_time", "category": "creator_profile", "creator_handle": "jaat.aesthetics", "content_id": null, "pipeline": "Slug-Ig-Crawler", "duration_ms": 125000, "status": "success", "error_type": null, "consumer_id": "default_consumer"}
{"event": "pipeline_active_time", "category": "creator_profile", "creator_handle": "jaat.aesthetics", "content_id": null, "pipeline": "Slug-Ig-Crawler", "duration_ms": 95000, "status": "success", "error_type": null, "consumer_id": "default_consumer"}
```

#### Post/Reel-Level Timing

**Location:** `selenium_backend.py` - `_scrape_and_close_tab()`

**Scope:** Wraps the full lifecycle of scraping one post/reel, including:
- Tab switching
- Title/metadata extraction
- Media extraction
- Likes extraction
- Comments extraction

**Category:** `creator_content`

**Content ID:** Uses post shortcode if available, otherwise falls back to post URL slug.

**Example Log Entries:**
```json
{"event": "pipeline_total_time", "category": "creator_content", "creator_handle": "jaat.aesthetics", "content_id": "ABC123xyz", "pipeline": "Slug-Ig-Crawler", "duration_ms": 8500, "status": "success", "error_type": null, "consumer_id": "default_consumer"}
{"event": "pipeline_active_time", "category": "creator_content", "creator_handle": "jaat.aesthetics", "content_id": "ABC123xyz", "pipeline": "Slug-Ig-Crawler", "duration_ms": 6200, "status": "success", "error_type": null, "consumer_id": "default_consumer"}
```

### Error Handling

Timing logs **always emit**, even on failure:
- On exception: `status = "error"`, `error_type = <exception class name>`
- After logging: Exception is re-raised (never swallowed)
- Both total and active time are recorded up to the point of failure

### Implementation Details

- **Clock:** Uses `time.perf_counter()` (monotonic clock) for precise measurements
- **Precision:** Durations converted to integer milliseconds
- **Independence:** Active and total time are measured independently with separate timers
- **Placement:** Timers wrap existing function boundaries, avoiding tight inner loops

### Use Cases

These timing logs enable:

1. **Latency Analysis:** Understand real-world scraping performance across profiles and posts
2. **Bottleneck Detection:** Identify slow operations by comparing active vs total time
3. **Cost Modeling:** Estimate resource costs based on active processing time
4. **Prometheus/Loki Ingestion:** Structured JSON format is ready for log aggregation systems
5. **Performance Regression Detection:** Track timing trends over time

### Example Analysis

```bash
# Extract profile-level timings
grep "pipeline_total_time.*creator_profile" scraper_log_*.log | jq '.duration_ms'

# Compare active vs total time for posts
grep "pipeline_.*_time.*creator_content" scraper_log_*.log | jq '{event, duration_ms}' | jq -s 'group_by(.event)'
```
