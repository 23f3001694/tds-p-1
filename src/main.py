"""
Main FastAPI application.

This is the entry point that:
1. Receives POST requests at /api-endpoint
2. Validates the secret and request structure
3. Returns immediate HTTP 200 response
4. Processes the request in background (generate code, create repo, notify)
"""

import json
import logging
from typing import Dict, Any
from pathlib import Path
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

from .config import Config
from .validator import RequestValidator
from .llm import CodeGenerator
from .github import GitHubClient
from .evaluator import EvaluationNotifier

# Configure logging
# Get the root logger and clear any existing handlers
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper()))

# Remove existing handlers
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Create formatter
formatter = logging.Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Add console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

# Add file handler if LOG_FILE is configured
if Config.LOG_FILE:
    Config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(Config.LOG_FILE)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

app = FastAPI(title="TDS Project 1 - Automated GitHub Pages Deployment")

logger.info("Application starting up")
if Config.LOG_FILE:
    logger.info(f"Logging to file: {Config.LOG_FILE}")
if Config.LOG_FILE:
    logger.info(f"Logging to file: {Config.LOG_FILE}")


class Storage:
    """Simple JSON file storage for tracking processed requests."""
    
    @staticmethod
    def load() -> Dict[str, Any]:
        """Load processed requests from disk."""
        if Config.STORAGE_PATH.exists():
            try:
                data = json.loads(Config.STORAGE_PATH.read_text())
                logger.debug(f"Loaded {len(data)} processed requests from storage")
                return data
            except Exception as e:
                logger.error(f"Failed to load storage: {e}")
                return {}
        return {}
    
    @staticmethod
    def save(data: Dict[str, Any]) -> None:
        """Save processed requests to disk."""
        Config.STORAGE_PATH.write_text(json.dumps(data, indent=2))
        logger.debug(f"Saved {len(data)} processed requests to storage")
    
    @staticmethod
    def get_key(data: Dict[str, Any]) -> str:
        """Generate unique key for a request."""
        return f"{data['email']}::{data['task']}::round{data['round']}::{data['nonce']}"


def process_request_background(data: Dict[str, Any]) -> None:
    """
    Background task that processes the request.
    
    This function:
    1. Generates code using LLM
    2. Creates/updates GitHub repository
    3. Commits files in correct order (LICENSE → attachments → README → index.html LAST)
    4. Enables GitHub Pages (round 1)
    5. Waits for pages deployment to complete
    6. Notifies evaluation server
    7. Saves processed state
    
    Note: index.html is committed LAST to ensure the deployment verification
    waits for the correct commit that triggers the GitHub Pages action.
    """
    round_num = data["round"]
    task_id = data["task"]
    
    logger.info(f"{'='*60}")
    logger.info(f"Processing Task: {task_id} (Round {round_num})")
    logger.info(f"Brief: {data['brief'][:80]}...")
    logger.info(f"{'='*60}")
    
    try:
        # Initialize clients
        logger.debug("Initializing clients")
        code_gen = CodeGenerator()
        github = GitHubClient()
        
        # Step 1: Get or create repository
        repo = github.get_or_create_repo(
            repo_name=task_id,
            description=f"Auto-generated for: {data['brief'][:100]}"
        )
        
        # Step 2: For round 2, get previous README and HTML for context
        prev_readme = None
        prev_html = None
        if round_num >= 2:
            prev_readme = github.get_readme_content(repo)
            prev_html = github.get_html_content(repo)
            if prev_readme:
                logger.info("Loaded previous README for context")
            if prev_html:
                logger.info(f"Loaded previous HTML for context ({len(prev_html)} chars)")
        
        # Step 3: Generate application code
        logger.info("Generating application code with LLM")
        result = code_gen.generate(
            brief=data["brief"],
            checks=data.get("checks", []),
            attachments=data.get("attachments", []),
            round_num=round_num,
            prev_readme=prev_readme,
            prev_html=prev_html
        )
        
        files = result
        saved_attachments = result.get("attachments", [])
        
        # Step 4: Commit MIT license FIRST (round 1 only)
        # This ensures index.html is committed last to trigger deployment
        if round_num == 1:
            logger.info("Committing LICENSE")
            license_text = GitHubClient.generate_mit_license()
            github.commit_file(
                repo=repo,
                path="LICENSE",
                content=license_text,
                message="Add MIT License"
            )
        
        # Step 5: Commit attachments SECOND (round 1 only)
        if round_num == 1 and saved_attachments:
            logger.info(f"Committing {len(saved_attachments)} attachments")
            for att in saved_attachments:
                att_path = Path(att["path"])
                try:
                    if att["mime"].startswith("text") or att_path.suffix in [".csv", ".json", ".txt", ".md"]:
                        # Text file
                        content = att_path.read_text(encoding="utf-8", errors="ignore")
                        github.commit_file(
                            repo=repo,
                            path=att["name"],
                            content=content,
                            message=f"Add attachment {att['name']}"
                        )
                    else:
                        # Binary file
                        content = att_path.read_bytes()
                        github.commit_binary_file(
                            repo=repo,
                            path=att["name"],
                            content=content,
                            message=f"Add binary attachment {att['name']}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to commit attachment {att['name']}: {e}")
        
        # Step 6: Commit README.md THIRD
        logger.info("Committing README.md")
        github.commit_file(
            repo=repo,
            path="README.md",
            content=files["README.md"],
            message=f"Generate README.md for round {round_num}"
        )
        
        # Step 7: Enable GitHub Pages (round 1 only) - BEFORE committing index.html
        pages_url = f"https://{github.username}.github.io/{task_id}/"
        if round_num == 1:
            logger.info("Enabling GitHub Pages")
            pages_ok = github.enable_pages(task_id)
            if not pages_ok:
                logger.warning("GitHub Pages might not be enabled. Using expected URL anyway.")
        
        # Step 8: Commit index.html LAST (this triggers the GitHub Pages deployment)
        logger.info("Committing index.html (FINAL - triggers deployment)")
        github.commit_file(
            repo=repo,
            path="index.html",
            content=files["index.html"],
            message=f"Generate index.html for round {round_num}"
        )
        
        # Step 9: Get latest commit SHA (should be the index.html commit)
        commit_sha = github.get_latest_commit_sha(repo)
        logger.info(f"Latest commit SHA: {commit_sha}")
        
        # Step 10: Wait for GitHub Pages deployment to complete
        logger.info(f"Waiting for GitHub Pages deployment of commit {commit_sha[:8]}...")
        pages_ready = github.wait_for_pages_deployment(repo, commit_sha)
        
        if not pages_ready:
            logger.warning("GitHub Pages deployment not confirmed, but proceeding with notification")
        
        # Step 11: Prepare notification payload
        payload = {
            "email": data["email"],
            "task": data["task"],
            "round": round_num,
            "nonce": data["nonce"],
            "repo_url": repo.html_url,
            "commit_sha": commit_sha,
            "pages_url": pages_url
        }
        
        logger.info(f"Repository: {repo.html_url}")
        logger.info(f"Pages URL: {pages_url}")
        logger.info(f"Commit SHA: {commit_sha}")
        
        # Step 12: Notify evaluation server
        EvaluationNotifier.notify(data["evaluation_url"], payload)
        
        # Step 13: Save processed state
        storage = Storage.load()
        storage[Storage.get_key(data)] = payload
        Storage.save(storage)
        
        logger.info(f"{'='*60}")
        logger.info(f"Completed Task: {task_id} (Round {round_num})")
        logger.info(f"{'='*60}")
        
    except Exception as e:
        logger.error(f"ERROR processing task {task_id}: {e}", exc_info=True)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "service": "TDS Project 1 - Automated GitHub Pages Deployment"
    }


@app.post("/api-endpoint")
async def receive_request(request: Request, background_tasks: BackgroundTasks):
    """
    Main endpoint for receiving task requests.
    
    This endpoint:
    1. Validates the request structure
    2. Verifies the secret
    3. Checks for duplicates
    4. Returns immediate HTTP 200
    5. Schedules background processing
    """
    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"Invalid JSON received: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    
    logger.info(f"{'='*60}")
    logger.info(f"Received request: {data.get('task', 'unknown')} (Round {data.get('round', '?')})")
    logger.info(f"{'='*60}")
    
    # Validate request structure
    is_valid, error_msg = RequestValidator.validate(data)
    if not is_valid:
        logger.warning(f"Validation error: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Verify secret
    if data.get("secret") != Config.USER_SECRET:
        logger.warning(f"Invalid secret provided for task: {data.get('task')}")
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    # Check for duplicate requests
    storage = Storage.load()
    key = Storage.get_key(data)
    
    if key in storage:
        logger.info("Duplicate request detected - re-notifying")
        # Re-notify evaluation server with previous result
        prev_payload = storage[key]
        EvaluationNotifier.notify(data["evaluation_url"], prev_payload)
        return JSONResponse({
            "status": "duplicate",
            "message": "Request already processed, re-notification sent",
            "previous_result": prev_payload
        })
    
    # Schedule background processing
    background_tasks.add_task(process_request_background, data)
    
    logger.info(f"Request accepted - processing in background")
    
    # Return immediate acknowledgment
    return JSONResponse({
        "status": "accepted",
        "message": f"Processing round {data['round']} for task {data['task']}"
    })
