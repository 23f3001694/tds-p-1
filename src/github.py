"""
GitHub operations module.

This module handles all interactions with GitHub:
1. Creating public repositories
2. Committing files (text and binary)
3. Enabling GitHub Pages
4. Generating MIT license
"""

from datetime import datetime
from typing import Optional
import logging
import httpx
from github import Github, GithubException

from .config import Config

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub API operations."""
    
    def __init__(self):
        self.client = Github(Config.GITHUB_TOKEN)
        self.username = Config.GITHUB_USERNAME
        self.user = self.client.get_user()
        logger.info(f"GitHubClient initialized for user: {self.username}")
    
    def get_or_create_repo(self, repo_name: str, description: str) -> any:
        """
        Get existing repo or create new public repo.
        
        Args:
            repo_name: Name of the repository
            description: Repository description
            
        Returns:
            GitHub repository object
        """
        try:
            # Try to get existing repo
            repo = self.user.get_repo(repo_name)
            logger.info(f"Repository '{repo_name}' already exists")
            return repo
        except GithubException as e:
            if e.status == 404:
                # Repo doesn't exist, create it
                logger.info(f"Creating new repository '{repo_name}'")
                repo = self.user.create_repo(
                    name=repo_name,
                    description=description,
                    private=False,
                    auto_init=False
                )
                logger.info(f"Repository created: {repo.html_url}")
                return repo
            else:
                logger.error(f"GitHub API error: {e}")
                raise
    
    def commit_file(self, repo: any, path: str, content: str, message: str) -> None:
        """
        Create or update a text file in the repository.
        
        Args:
            repo: GitHub repository object
            path: File path in the repository
            content: File content (string)
            message: Commit message
        """
        try:
            # Try to get existing file
            existing = repo.get_contents(path)
            # File exists, update it
            repo.update_file(
                path=path,
                message=message,
                content=content,
                sha=existing.sha
            )
            logger.info(f"Updated {path} in {repo.full_name}")
        except GithubException as e:
            if e.status == 404:
                # File doesn't exist, create it
                repo.create_file(
                    path=path,
                    message=message,
                    content=content
                )
                logger.info(f"Created {path} in {repo.full_name}")
            else:
                logger.error(f"Error committing {path}: {e}")
                raise
    
    def commit_binary_file(self, repo: any, path: str, content: bytes, message: str) -> None:
        """
        Create or update a binary file in the repository.
        
        Args:
            repo: GitHub repository object
            path: File path in the repository
            content: File content (bytes)
            message: Commit message
        """
        try:
            # Try to get existing file
            existing = repo.get_contents(path)
            # File exists, update it
            repo.update_file(
                path=path,
                message=message,
                content=content,
                sha=existing.sha
            )
            logger.info(f"Updated binary {path} in {repo.full_name}")
        except GithubException as e:
            if e.status == 404:
                # File doesn't exist, create it
                repo.create_file(
                    path=path,
                    message=message,
                    content=content
                )
                logger.info(f"Created binary {path} in {repo.full_name}")
            else:
                logger.error(f"Error committing binary {path}: {e}")
                raise
    
    def enable_pages(self, repo_name: str, branch: str = "main") -> bool:
        """
        Enable GitHub Pages for the repository using REST API.
        
        Args:
            repo_name: Name of the repository
            branch: Branch to deploy from (default: main)
            
        Returns:
            True if successful, False otherwise
        """
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/pages"
        headers = {
            "Authorization": f"token {Config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "source": {
                "branch": branch,
                "path": "/"
            }
        }
        
        try:
            logger.debug(f"Enabling GitHub Pages for {repo_name}")
            response = httpx.post(url, headers=headers, json=data, timeout=30.0)
            
            if response.status_code in (201, 204, 409):
                # 201: Created, 204: No Content, 409: Already exists
                logger.info(f"GitHub Pages enabled for {repo_name}")
                return True
            else:
                logger.warning(f"Pages API returned {response.status_code}: {response.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"Failed to enable Pages: {e}")
            return False
    
    def get_latest_commit_sha(self, repo: any) -> Optional[str]:
        """
        Get the SHA of the latest commit.
        
        Args:
            repo: GitHub repository object
            
        Returns:
            Commit SHA or None if no commits
        """
        try:
            commits = repo.get_commits()
            sha = commits[0].sha
            logger.debug(f"Latest commit SHA: {sha}")
            return sha
        except Exception as e:
            logger.error(f"Failed to get commit SHA: {e}")
            return None
    
    def get_readme_content(self, repo: any) -> Optional[str]:
        """
        Get content of README.md from repository (for round 2 context).
        
        Args:
            repo: GitHub repository object
            
        Returns:
            README content as string or None if not found
        """
        try:
            readme = repo.get_contents("README.md")
            content = readme.decoded_content.decode("utf-8", errors="ignore")
            logger.info(f"Loaded README.md ({len(content)} chars)")
            return content
        except Exception as e:
            logger.warning(f"Could not load README.md: {e}")
            return None
    
    def get_html_content(self, repo: any) -> Optional[str]:
        """
        Get content of index.html from repository (for round 2 context).
        
        Args:
            repo: GitHub repository object
            
        Returns:
            HTML content as string or None if not found
        """
        try:
            html_file = repo.get_contents("index.html")
            content = html_file.decoded_content.decode("utf-8", errors="ignore")
            logger.info(f"Loaded index.html ({len(content)} chars)")
            return content
        except Exception as e:
            logger.warning(f"Could not load index.html: {e}")
            return None
    
    @staticmethod
    def generate_mit_license(owner: str = None) -> str:
        """
        Generate MIT license text.
        
        Args:
            owner: Copyright holder name (defaults to GITHUB_USERNAME)
            
        Returns:
            MIT license text
        """
        year = datetime.now().year
        owner = owner or Config.GITHUB_USERNAME
        
        return f"""MIT License

Copyright (c) {year} {owner}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
