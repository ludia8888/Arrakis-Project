"""
Git utilities for getting current commit hash
"""
import os
import subprocess
from functools import lru_cache


@lru_cache(maxsize = 1)
def get_current_commit_hash() -> str:
 """
 Get the current git commit hash
 Returns 'development' if not in a git repository
 """
 try:
 # Check if we're in a git repository
 if not os.path.exists(".git"):
 return "development"

 # Get the current commit hash
 result = subprocess.run(
 ["git", "rev-parse", "HEAD"], capture_output = True, text = True, check = True
 )

 commit_hash = result.stdout.strip()

 # Also check if there are uncommitted changes
 status_result = subprocess.run(
 ["git", "status", "--porcelain"], capture_output = True, text = True, check = True
 )

 if status_result.stdout.strip():
 # There are uncommitted changes
 commit_hash += "-dirty"

 return commit_hash[:12] # Return first 12 characters

 except (subprocess.CalledProcessError, FileNotFoundError):
 # Git not available or not a git repository
 return "development"
 except Exception:
 return "unknown"


def get_git_branch() -> str:
 """Get current git branch name"""
 try:
 result = subprocess.run(
 ["git", "rev-parse", "--abbrev-re", "HEAD"],
 capture_output = True,
 text = True,
 check = True,
 )
 return result.stdout.strip()
 except FileNotFoundError as e:
 # Git command not found
 import logging

 logger = logging.getLogger(__name__)
 logger.warning(f"Git command not found: {e}")
 return "unknown"
 except subprocess.CalledProcessError as e:
 # Git command failed (not a repo, corrupted repo, etc.)
 import logging

 logger = logging.getLogger(__name__)
 logger.warning(f"Git command failed: {e}")
 return "unknown"
 except Exception as e:
 # Log unexpected git errors for debugging
 import logging

 logger = logging.getLogger(__name__)
 logger.error(f"Unexpected git branch detection error: {e}", exc_info = True)
 return "unknown"
