# TDS Project 1 - Automated GitHub Pages Deployment System

A minimal, modular system that automatically generates web applications using LLM, deploys them to GitHub Pages, and notifies evaluation servers. Built for the Tools in Data Science (TDS) course.

## Architecture Overview

This system receives task briefs via HTTP POST, generates complete web applications using Groq AI, commits them to GitHub repositories, enables GitHub Pages, and notifies evaluation servers with deployment details.

### System Flow

```
1. POST Request → /api-endpoint
2. Validate secret & request structure
3. Return immediate HTTP 200
4. Background Processing:
   ├─ Generate code with Groq LLM
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
- `CodeGenerator`: Calls Groq API to generate HTML/CSS/JS and README

**Process:**
1. Decodes attachments from data URIs
2. Builds detailed prompt with brief, checks, and attachment info
3. Calls Groq's `llama-3.3-70b-versatile` model
4. Parses response to extract `index.html` and `README.md`
5. Falls back to minimal template if API fails

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
- Groq API key

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
- `GITHUB_TOKEN`: GitHub Personal Access Token with `repo` and `workflow` scopes
- `GITHUB_USERNAME`: Your GitHub username
- `GROQ_API_KEY`: API key from console.groq.com
- `USER_SECRET`: Secret string for request authentication

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
   - Call Groq API to generate code
   - Create GitHub repository (or get existing for round 2)
   - Commit generated files
   - Commit attachments (round 1)
   - Add MIT license (round 1)
   - Enable GitHub Pages (round 1)
   - Get latest commit SHA
   - Notify evaluation server with retry logic
   - Save processed state

### Round 1 vs Round 2

**Round 1** (Initial Build):
- Creates new repository
- Generates fresh code from brief
- Commits all attachments to repo
- Adds MIT LICENSE
- Enables GitHub Pages
- Notifies evaluation server

**Round 2** (Revision):
- Uses existing repository
- Fetches previous README and index.html for context
- Generates updated code based on new brief
- Commits updated files
- Pages already enabled, just updates content
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
- **groq**: Groq AI API client for LLM code generation
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
- **LLM API Failure**: Falls back to minimal HTML template
- **GitHub API Failure**: Logs error, continues with available operations
- **Evaluation Notification Failure**: Retries with exponential backoff

## Troubleshooting

### Configuration Issues
```bash
# Validate environment variables are loaded
uv run python -c "from src.config import Config; Config.validate(); print('OK')"
```

### Testing Groq API
```bash
# Test Groq connectivity
uv run python -c "from src.llm import CodeGenerator; gen = CodeGenerator(); print('Groq OK')"
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
- Code generation status
- GitHub operations (repo creation, commits, Pages enablement)
- Evaluation notification attempts
- Error traces

## Development Notes

### Design Principles

1. **Minimal**: No unnecessary features or dependencies
2. **Modular**: Each module has a single responsibility
3. **Fail-Fast**: Configuration validated at startup
4. **Resilient**: Retries for network operations, fallbacks for LLM
5. **Transparent**: Extensive logging for debugging

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

## License

MIT License - See generated repositories for full license text.

## Support

This is an educational project for TDS course. For issues:
1. Check environment variables are correctly set
2. Review server logs for error messages
3. Verify GitHub token has required scopes
4. Confirm Groq API key is valid
