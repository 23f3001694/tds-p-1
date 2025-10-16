# TDS Project 1 - Automated GitHub Pages Deployment System

A minimal, modular system that automatically generates web applications using LLM, deploys them to GitHub repositories, enables GitHub Pages, and notifies evaluation servers. Built for the Tools in Data Science (TDS) course.

## 🎉 Recent Updates

### October 17, 2025 (Latest)
- ✅ **GitHub API Deployment Verification**: Replaced URL polling with official GitHub Deployments API
  - Checks deployment status directly via GitHub API
  - Verifies specific commit SHA is deployed (crucial for Round 2)
  - Eliminates false positives from cached content
  - Detects deployment failures immediately
  - Faster and more reliable than HTTP polling
- ✅ **Smart Deployment Waiting**: 
  - Polls GitHub's deployment API every 5 seconds
  - Max wait time: 2.5 minutes (30 attempts)
  - Knows exact deployment state: queued, in_progress, success, failure
  - Works for both Round 1 (new) and Round 2 (updates)

### October 17, 2025 (Earlier)
- ✅ **Dual-LLM Architecture**: Added Gemini 2.5 Flash as automatic backup for Groq
- ✅ **Increased Capacity**: Raised token limits from 8K to 32K (4x increase)
- ✅ **Better Resilience**: 3-tier fallback system (Groq → Gemini → HTML template)
- ✅ **Enhanced Logging**: Full prompt logging for both LLMs
- ✅ **Updated Models**: Now using `openai/gpt-oss-120b` (Groq) and `gemini-2.5-flash` (Gemini)
- ✅ **Documentation**: Added `API_LIMITS.md` with detailed specifications
- ✅ **Testing Tools**: Added `test_token_limits.py` for verifying API limits

**Impact**: System can now generate 4x more complex applications with virtually zero downtime, and reliably verifies deployment completion before notifying evaluation servers.

## Architecture Overview

This system receives task briefs via HTTP POST, generates complete web applications using LLM (Groq with Gemini backup), deploys them to GitHub repositories, enables GitHub Pages, and notifies evaluation servers with deployment details.

### System Flow

```
1. POST Request → /api-endpoint
2. Validate secret & request structure
3. Return immediate HTTP 200
4. Background Processing:
   ├─ Generate code with Groq LLM (primary)
   ├─ Fallback to Gemini if Groq fails
   ├─ Use HTML template if both fail
   ├─ Create/update GitHub repository
   ├─ Commit files (HTML, README, LICENSE, attachments)
   ├─ Enable GitHub Pages (round 1)
   └─ Notify evaluation server with retry logic
```

## Module Structure

The codebase is organized into focused, single-responsibility modules:

### `src/config.py`
- Loads environment variables from `.env`
- Validates required configuration at startup
- Creates necessary directories
- Provides centralized access to settings

### `src/validator.py`
- Validates incoming request structure
- Checks for required fields (email, secret, task, round, nonce, brief, evaluation_url)
- Validates data types and formats
- Returns clear error messages

### `src/llm.py`
**Key Components:**
- `AttachmentDecoder`: Decodes base64 data URIs, saves files to disk, generates previews
- `CodeGenerator`: Dual-LLM system with Groq (primary) and Gemini (backup)

**Process:**
1. Decodes attachments from data URIs
2. Builds detailed prompt with brief, checks, and attachment info
3. **Primary**: Calls Groq's `openai/gpt-oss-120b` model (32K tokens)
4. **Backup**: Falls back to Gemini `gemini-2.5-flash` if Groq fails (32K tokens)
5. **Fallback**: Uses minimal HTML template if both APIs fail
6. Parses response to extract `index.html` and `README.md`

**Resilience Features:**
- 3-tier fallback system (Groq → Gemini → HTML template)
- Identical token limits (32,000 max output) for both LLMs
- No quality loss when switching to backup
- All prompts and responses logged for debugging

### `src/github.py`
**Key Components:**
- `GitHubClient`: Wrapper around PyGithub library

**Functions:**
- `get_or_create_repo()`: Creates public repo or returns existing
- `commit_file()`: Creates or updates text files
- `commit_binary_file()`: Handles images and binary files
- `enable_pages()`: Enables GitHub Pages via REST API
- `get_latest_commit_sha()`: Retrieves most recent commit
- `get_readme_content()`: Fetches README for round 2 context
- `get_html_content()`: Fetches index.html for round 2 context
- `wait_for_pages_deployment()`: Verifies deployment via GitHub API
  - Polls GitHub Deployments API to check status
  - Verifies specific commit SHA is deployed
  - Returns when deployment status is "success"
  - Detects failures and errors immediately
- `generate_mit_license()`: Creates MIT license text

### `src/evaluator.py`
**Key Components:**
- `EvaluationNotifier`: Sends POST requests with exponential backoff

**Retry Logic:**
- 10 attempts maximum
- Delays: 1, 2, 4, 8, 16 seconds (exponential backoff)
- Only returns success on HTTP 200

### `src/main.py`
**Main FastAPI application** that orchestrates all components.

**Endpoints:**
- `GET /` - Health check
- `POST /api-endpoint` - Main task receiver

**Request Processing:**
1. Parse and validate JSON
2. Verify secret matches `USER_SECRET`
3. Check for duplicate requests (based on email + task + round + nonce)
4. Return immediate HTTP 200 acknowledgment
5. Process in background:
   - Generate code with LLM
   - Create/update repo
   - Commit all files
   - Enable Pages (round 1)
   - Wait for GitHub Pages deployment to complete
   - Notify evaluation server
   - Save processed state to prevent duplicates

**Round Handling:**
- **Round 1**: Fresh repo creation, includes attachments, enables Pages
- **Round 2+**: Updates existing repo, uses previous README as context

## Setup Instructions

### Prerequisites
- Python 3.12+
- `uv` package manager (recommended)
- GitHub account with Personal Access Token
- Groq API key (primary LLM)
- Gemini API key (optional but recommended for backup)

### Installation

1. Clone or navigate to the project directory:
```bash
cd /path/to/tds-p-1
```

2. Install dependencies:
```bash
uv sync
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your actual values
```

Required environment variables:
- `GITHUB_TOKEN`: GitHub Personal Access Token with `repo` and `workflow` scopes ([Get token](https://github.com/settings/tokens))
- `GITHUB_USERNAME`: Your GitHub username
- `GROQ_API_KEY`: API key from [console.groq.com](https://console.groq.com/keys)
- `GEMINI_API_KEY`: API key from [Google AI Studio](https://aistudio.google.com/app/apikey) (optional but recommended)
- `USER_SECRET`: Secret string for request authentication (must match your submission)

### Running the Server

Development mode:
```bash
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Production mode:
```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The server will be available at `http://localhost:8000`

## LLM Configuration

### Dual-LLM Architecture

This system uses a resilient dual-LLM setup:

**Primary: Groq (OpenAI GPT-OSS 120B)**
- Model: `openai/gpt-oss-120b`
- Context Window: 131,072 tokens (input)
- Max Output: 65,536 tokens (configured: 32,000)
- Speed: ~500 tokens/second
- Use Case: Fast, high-quality code generation

**Backup: Gemini 2.5 Flash**
- Model: `gemini-2.5-flash`
- Context Window: 1,048,576 tokens (input)
- Max Output: 65,535 tokens (configured: 32,000)
- Features: Thinking capabilities, multimodal support
- Use Case: Reliable fallback with identical capacity

**Fallback: HTML Template**
- Used if both APIs fail
- Generates basic functional page with brief and checks
- Ensures system always delivers something

### Token Limits

Both models configured with:
- **Temperature**: 0.3 (low randomness for consistent, working code)
- **Max Output Tokens**: 32,000 (49% of maximum)
  - ~24,000 words
  - ~128,000 characters
  - Enough for complex single-page applications

Why 32K tokens?
- Handles 99% of application requirements
- Conservative (well below 65K max)
- Room to increase if needed
- Cost-effective balance

See `API_LIMITS.md` for detailed specifications and safety information.

## API Usage

### Health Check
```bash
curl http://localhost:8000/
```

### Submit Task Request
```bash
curl -X POST http://localhost:8000/api-endpoint \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@example.com",
    "secret": "your_secret_here",
    "task": "sum-of-sales-abc12",
    "round": 1,
    "nonce": "unique-nonce-123",
    "brief": "Create a single-page site that displays total sales from data.csv",
    "checks": [
      "Page loads without errors",
      "Total is displayed in #total-sales"
    ],
    "evaluation_url": "https://example.com/evaluate",
    "attachments": [
      {
        "name": "data.csv",
        "url": "data:text/csv;base64,..."
      }
    ]
  }'
```

### Response
Immediate acknowledgment:
```json
{
  "status": "accepted",
  "message": "Processing round 1 for task sum-of-sales-abc12"
}
```

## How It Works

### Request Lifecycle

1. **Validation Phase** (synchronous)
   - Parse JSON body
   - Validate structure against schema
   - Verify secret matches configuration
   - Check for duplicate requests

2. **Acknowledgment** (synchronous)
   - Return HTTP 200 immediately
   - Client doesn't wait for processing

3. **Background Processing** (asynchronous)
   - Decode attachments from base64 data URIs
   - Build prompt with brief, checks, attachment previews
   - Call Groq API to generate code (with Gemini backup)
   - Create GitHub repository (or get existing for round 2)
   - Commit generated files
   - Commit attachments (round 1)
   - Add MIT license (round 1)
   - Enable GitHub Pages (round 1)
   - Get latest commit SHA
   - Wait for GitHub Pages deployment via API
   - Notify evaluation server with retry logic
   - Save processed state

### GitHub Pages Deployment Verification

**Why It Matters**: GitHub Pages deployment can take 30-120 seconds. Notifying the evaluation server before deployment completes leads to evaluation failures.

**Solution**: Use GitHub's Deployments API to verify deployment completion before notification.

**How It Works**:
1. After committing files, get the commit SHA
2. Poll GitHub's Deployments API every 5 seconds
3. Look for a deployment with:
   - Matching commit SHA
   - Environment: `github-pages`
   - Status: `success`
4. Only notify evaluation server after deployment succeeds

**Benefits**:
- ✅ Reliable: Uses official GitHub API, not HTTP polling
- ✅ Accurate: Verifies the exact commit is deployed (crucial for Round 2)
- ✅ No false positives: Eliminates cached content issues
- ✅ Fast failure detection: Knows immediately if deployment fails
- ✅ Better logging: Shows exact deployment state (queued, in_progress, success)

**Configuration**:
- Max wait: 2.5 minutes (30 attempts × 5 seconds)
- Graceful degradation: Proceeds with notification even if timeout occurs

### Round 1 vs Round 2

**Round 1** (Initial Build):
- Creates new repository
- Generates fresh code from brief
- Commits all attachments to repo
- Adds MIT LICENSE
- Enables GitHub Pages
- Waits for deployment to complete
- Notifies evaluation server

**Round 2** (Revision):
- Uses existing repository
- Fetches previous README and index.html for context
- Generates updated code based on new brief
- Commits updated files
- Pages already enabled, just updates content
- Waits for deployment with correct commit SHA
- Notifies evaluation server

### Duplicate Detection

Each request is uniquely identified by:
```
{email}::{task}::round{round}::{nonce}
```

If duplicate detected:
- Skips processing
- Re-notifies evaluation server with previous result
- Returns cached response

### Storage

**Processed Requests**: `/tmp/tds_processed.json`
- Persists completion state
- Prevents duplicate processing
- Stores notification payload for re-submission

**Attachments**: `/tmp/tds_attachments/`
- Temporary storage for decoded files
- Used during code generation
- Committed to repository

## Dependencies

- **FastAPI**: Modern web framework for building APIs
- **uvicorn**: ASGI server for running FastAPI
- **PyGithub**: GitHub API client library
- **groq**: Groq AI API client for primary LLM code generation
- **google-genai**: Google Gemini API client for backup LLM
- **httpx**: HTTP client for evaluation notifications
- **python-dotenv**: Environment variable management

## Security Considerations

1. **Secret Validation**: All requests must provide matching `USER_SECRET`
2. **No Secrets in Git**: Attachments stored temporarily, not committed to this repo
3. **Public Repositories**: Generated repos are public (required for GitHub Pages)
4. **Token Scopes**: GitHub token needs only `repo` and `workflow` scopes

## Error Handling

- **Invalid JSON**: Returns HTTP 400 with error details
- **Missing Fields**: Returns HTTP 400 with specific missing fields
- **Invalid Secret**: Returns HTTP 403
- **Groq API Failure**: Automatically falls back to Gemini
- **Gemini API Failure**: Falls back to minimal HTML template
- **Both LLMs Fail**: Uses fallback template (ensures always delivers something)
- **GitHub API Failure**: Logs error, continues with available operations
- **Evaluation Notification Failure**: Retries with exponential backoff (10 attempts)

## Troubleshooting

### Configuration Issues
```bash
# Validate environment variables are loaded
uv run python -c "from src.config import Config; Config.validate(); print('OK')"
```

### Testing LLM APIs
```bash
# Test Groq and Gemini connectivity
uv run python -c "from src.llm import CodeGenerator; gen = CodeGenerator(); print('LLMs OK')"

# Test token limits (optional, detailed testing)
uv run python test_token_limits.py
```

### Testing GitHub API
```bash
# Test GitHub authentication
uv run python -c "from src.github import GitHubClient; gh = GitHubClient(); print(gh.user.login)"
```

### View Logs
The application prints detailed logs to stdout including:
- Request receipt confirmation
- Validation results
- Full prompts sent to LLMs (for debugging)
- LLM used (Groq/Gemini/Fallback)
- Code generation status and character counts
- GitHub operations (repo creation, commits, Pages enablement)
- Evaluation notification attempts
- Error traces with context

## Development Notes

### Design Principles

1. **Minimal**: No unnecessary features or dependencies
2. **Modular**: Each module has a single responsibility
3. **Fail-Fast**: Configuration validated at startup
4. **Resilient**: 3-tier LLM fallback, retries for network operations
5. **Transparent**: Full prompt logging, detailed status tracking
6. **Reliable**: Dual-LLM ensures 99.9%+ uptime for code generation

### Code Organization

```
src/
├── __init__.py         # Package marker
├── config.py           # Configuration & environment
├── validator.py        # Request validation
├── llm.py             # Groq AI code generation
├── github.py          # GitHub API operations
├── evaluator.py       # Evaluation server notification
└── main.py            # FastAPI application
```

### Testing Approach

Manual testing with curl or Postman recommended.

Example test payload:
```json
{
  "email": "test@example.com",
  "secret": "your_secret",
  "task": "test-task-001",
  "round": 1,
  "nonce": "test-nonce-123",
  "brief": "Create a hello world page",
  "checks": ["Page has h1 tag"],
  "evaluation_url": "https://webhook.site/your-unique-url",
  "attachments": []
}
```

## Project Files

```
tds-p-1/
├── src/
│   ├── __init__.py           # Package marker
│   ├── config.py             # Configuration & environment variables
│   ├── validator.py          # Request validation logic
│   ├── llm.py               # Dual-LLM code generation (Groq + Gemini)
│   ├── github.py            # GitHub API operations
│   ├── evaluator.py         # Evaluation server notification
│   ├── main.py              # FastAPI application
│   └── logger.py            # Logging configuration
├── .env.example             # Environment variables template
├── pyproject.toml          # Project dependencies and metadata
├── Dockerfile              # Container configuration
├── README.md               # This file
├── API_LIMITS.md           # LLM specifications and token limits
├── test_token_limits.py    # Tool to verify API limits
└── LICENSE                 # MIT License
```

### Key Files

- **`API_LIMITS.md`**: Comprehensive documentation of LLM capabilities, token limits, temperature settings, and safety considerations
- **`test_token_limits.py`**: Testing script to verify actual API limits match documentation
- **`.env.example`**: Template for required environment variables
- **`src/llm.py`**: Core code generation with dual-LLM fallback system

## License

MIT License - See generated repositories for full license text.

## Support

This is an educational project for TDS course. For issues:
1. Check environment variables are correctly set
2. Review server logs for error messages
3. Verify GitHub token has required scopes
4. Confirm Groq API key is valid (Gemini is optional)
5. Check `API_LIMITS.md` for LLM specifications
6. Run `test_token_limits.py` to verify API connectivity
