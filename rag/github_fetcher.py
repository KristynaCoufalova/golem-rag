"""
GitHub API client for fetching source files.

Optimized for building vector databases from GitHub repositories.
Uses tree endpoint for efficient file listing and git diff for change detection.
"""

import os
import hashlib
import time
from typing import List, Dict, Optional, Set
from pathlib import Path
import requests
from urllib.parse import quote


class GitHubFetcher:
    """
    GitHub API client for fetching repository files.
    
    Optimized for:
    - Tree endpoint for fast file listing (cached)
    - Git diff for change detection
    - Rate limit handling
    """
    
    def __init__(
        self,
        repo: str,
        token: Optional[str] = None,
        branch: str = "main",
        cache_dir: Optional[str] = None
    ):
        """
        Initialize GitHub fetcher.
        
        Args:
            repo: Repository in format "owner/repo" or full URL "https://github.com/owner/repo"
            token: GitHub personal access token (read-only scope: repo:read)
            branch: Branch name (default: "main")
            cache_dir: Directory for caching API responses (optional)
        """
        # Extract owner/repo from URL if needed
        if repo.startswith("http"):
            # Extract from URL like https://github.com/owner/repo or https://github.com/owner/repo.git
            import re
            match = re.search(r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$', repo)
            if match:
                self.owner = match.group(1)
                self.repo_name = match.group(2)
                self.repo = f"{self.owner}/{self.repo_name}"
            else:
                raise ValueError(f"Could not extract owner/repo from URL: {repo}")
        else:
            # Assume format "owner/repo"
            self.repo = repo
            parts = repo.split("/", 1)
            if len(parts) != 2:
                raise ValueError(f"Repository must be in format 'owner/repo', got: {repo}")
            self.owner, self.repo_name = parts
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.branch = branch
        self.base_url = "https://api.github.com"
        
        # Cache directory for API responses
        if cache_dir:
            self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.cache_dir = None
        
        # Session for connection pooling
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            })
        
        # Cache for tree data (in-memory)
        self._tree_cache: Optional[Dict] = None
        self._tree_cache_time: float = 0
        self._tree_cache_ttl: int = 300  # 5 minutes
    
    def _get_cache_key(self, endpoint: str) -> str:
        """Generate cache key for endpoint."""
        return hashlib.md5(f"{self.repo}:{self.branch}:{endpoint}".encode()).hexdigest()
    
    def _get_cached_response(self, endpoint: str) -> Optional[Dict]:
        """Get cached API response if available."""
        if not self.cache_dir:
            return None
        
        cache_key = self._get_cache_key(endpoint)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            import json
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return None
        
        return None
    
    def _cache_response(self, endpoint: str, data: Dict):
        """Cache API response."""
        if not self.cache_dir:
            return
        
        cache_key = self._get_cache_key(endpoint)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        import json
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass
    
    def _make_request(self, endpoint: str, use_cache: bool = True) -> Dict:
        """
        Make GitHub API request with caching and rate limit handling.
        
        Automatically retries on rate limit by sleeping until reset time.
        
        Args:
            endpoint: API endpoint (e.g., "/repos/owner/repo/git/trees/main")
            use_cache: Whether to use cache (default: True)
        
        Returns:
            JSON response as dictionary
        """
        # Check cache first
        if use_cache:
            cached = self._get_cached_response(endpoint)
            if cached:
                return cached
        
        url = f"{self.base_url}{endpoint}"
        
        # Retry loop for rate limit handling
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = self.session.get(url)
                
                # Handle rate limit (403 with X-RateLimit-Remaining = 0)
                if response.status_code == 403:
                    rate_limit_remaining = response.headers.get("X-RateLimit-Remaining", "1")
                    if rate_limit_remaining == "0":
                        reset_timestamp = int(response.headers.get("X-RateLimit-Reset", "0"))
                        if reset_timestamp > 0:
                            current_time = int(time.time())
                            sleep_seconds = max(0, reset_timestamp - current_time + 5)  # Add 5s buffer
                            
                            if sleep_seconds > 0:
                                print(f"   ⏳ Rate limited. Sleeping {sleep_seconds}s until reset...")
                                time.sleep(sleep_seconds)
                                retry_count += 1
                                continue
                
                response.raise_for_status()
                data = response.json()
                
                # Cache the response
                if use_cache:
                    self._cache_response(endpoint, data)
                
                return data
            
            except requests.exceptions.HTTPError as e:
                if response.status_code == 404:
                    # More helpful error message
                    if "repos" in endpoint:
                        raise ValueError(
                            f"Repository not found: {self.repo}\n"
                            f"Possible reasons:\n"
                            f"  - Repository is private (needs token with repo:read scope)\n"
                            f"  - Repository doesn't exist or name is incorrect\n"
                            f"  - Branch doesn't exist\n"
                            f"URL: {url}"
                        )
                    else:
                        raise ValueError(f"Resource not found: {url}")
                elif response.status_code == 403:
                    # Rate limit that we couldn't handle
                    rate_limit_remaining = response.headers.get("X-RateLimit-Remaining", "0")
                    if rate_limit_remaining == "0":
                        reset_time = response.headers.get("X-RateLimit-Reset", "0")
                        raise ValueError(
                            f"GitHub API rate limit exceeded after retries. "
                            f"Reset at: {reset_time}. "
                            f"Use a token to increase limits."
                        )
                    raise
                else:
                    raise
    
    def get_default_branch(self) -> str:
        """
        Get default branch name for repository.
        
        Returns:
            Default branch name (e.g., "main" or "master")
        """
        endpoint = f"/repos/{self.owner}/{self.repo_name}"
        data = self._make_request(endpoint)
        return data.get("default_branch", "main")
    
    def get_current_commit_sha(self, branch: Optional[str] = None) -> str:
        """
        Get current commit SHA for branch.
        
        Args:
            branch: Branch name (default: self.branch, falls back to default branch)
        
        Returns:
            Commit SHA string
        """
        branch = branch or self.branch
        
        # Try to get commit SHA
        try:
            endpoint = f"/repos/{self.owner}/{self.repo_name}/commits/{branch}"
            data = self._make_request(endpoint)
            return data["sha"]
        except ValueError as e:
            # If branch doesn't exist, try default branch
            if "404" in str(e) or "Not Found" in str(e):
                print(f"   ⚠️  Branch '{branch}' not found, trying default branch...")
                default_branch = self.get_default_branch()
                if default_branch != branch:
                    print(f"   📌 Using default branch: {default_branch}")
                    endpoint = f"/repos/{self.owner}/{self.repo_name}/commits/{default_branch}"
                    data = self._make_request(endpoint)
                    self.branch = default_branch  # Update to default branch
                    return data["sha"]
            raise
    
    def get_file_tree(
        self,
        file_extensions: Optional[List[str]] = None,
        recursive: bool = True
    ) -> List[Dict[str, str]]:
        """
        Get file tree using GitHub tree API (fast, efficient).
        
        Args:
            file_extensions: List of file extensions to filter (e.g., [".py", ".ts"])
            recursive: Whether to get recursive tree (default: True)
        
        Returns:
            List of file info dicts with keys: path, sha, type, size
        """
        # Check in-memory cache first
        if self._tree_cache and (time.time() - self._tree_cache_time) < self._tree_cache_ttl:
            files = self._tree_cache.get("files", [])
        else:
            # Get commit SHA for branch
            commit_sha = self.get_current_commit_sha()
            
            # Get tree recursively
            endpoint = f"/repos/{self.owner}/{self.repo_name}/git/trees/{commit_sha}"
            if recursive:
                endpoint += "?recursive=1"
            
            tree_data = self._make_request(endpoint, use_cache=True)
            
            # Extract files from tree
            files = []
            if "tree" in tree_data:
                for item in tree_data["tree"]:
                    if item["type"] == "blob":  # blob = file
                        files.append({
                            "path": item["path"],
                            "sha": item["sha"],
                            "type": item["type"],
                            "size": item.get("size", 0)
                        })
            
            # Cache in memory
            self._tree_cache = {"files": files, "commit_sha": commit_sha}
            self._tree_cache_time = time.time()
        
        # Filter by file extensions if provided
        if file_extensions:
            file_extensions = [ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in file_extensions]
            files = [
                f for f in files
                if any(f["path"].lower().endswith(ext) for ext in file_extensions)
            ]
        
        return files
    
    def get_file_content(self, path: str, sha: Optional[str] = None) -> str:
        """
        Get file content from GitHub.
        
        Args:
            path: File path in repository
            sha: Optional file SHA (if None, will fetch from current branch)
        
        Returns:
            File content as string
        """
        if sha:
            # Use blob API with SHA
            endpoint = f"/repos/{self.owner}/{self.repo_name}/git/blobs/{sha}"
            blob_data = self._make_request(endpoint)
            
            # Decode base64 content
            import base64
            content = base64.b64decode(blob_data["content"]).decode("utf-8")
            return content
        else:
            # Use contents API (simpler, but requires path)
            endpoint = f"/repos/{self.owner}/{self.repo_name}/contents/{quote(path)}"
            file_data = self._make_request(endpoint)
            
            # Decode base64 content
            import base64
            content = base64.b64decode(file_data["content"]).decode("utf-8")
            return content
    
    def get_changed_files(self, since_sha: str) -> List[Dict[str, str]]:
        """
        Get changed files since commit SHA using git diff.
        
        Args:
            since_sha: Commit SHA to compare from
        
        Returns:
            List of changed file info dicts with keys: path, status, sha
        """
        current_sha = self.get_current_commit_sha()
        
        # Use compare API
        endpoint = f"/repos/{self.owner}/{self.repo_name}/compare/{since_sha}...{current_sha}"
        compare_data = self._make_request(endpoint)
        
        changed_files = []
        if "files" in compare_data:
            for file_info in compare_data["files"]:
                changed_files.append({
                    "path": file_info["filename"],
                    "status": file_info["status"],  # added, modified, removed
                    "sha": file_info.get("sha", ""),
                    "additions": file_info.get("additions", 0),
                    "deletions": file_info.get("deletions", 0)
                })
        
        return changed_files
    
    def fetch_all_files(
        self,
        file_extensions: Optional[List[str]] = None,
        max_files: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Fetch all files with their content.
        
        Args:
            file_extensions: List of file extensions to filter
            max_files: Maximum number of files to fetch (for testing)
        
        Returns:
            List of file dicts with keys: path, content, sha, size
        """
        print(f"📋 Getting file tree for {self.repo} (branch: {self.branch})...")
        files = self.get_file_tree(file_extensions=file_extensions)
        
        if max_files:
            files = files[:max_files]
        
        print(f"   Found {len(files)} files")
        
        # Fetch content for each file
        files_with_content = []
        for i, file_info in enumerate(files, 1):
            try:
                print(f"   [{i}/{len(files)}] Fetching: {file_info['path']}")
                content = self.get_file_content(path=file_info["path"], sha=file_info["sha"])
                
                files_with_content.append({
                    "path": file_info["path"],
                    "content": content,
                    "sha": file_info["sha"],
                    "size": file_info["size"]
                })
            except Exception as e:
                print(f"   ⚠️  Error fetching {file_info['path']}: {e}")
                continue
        
        return files_with_content
