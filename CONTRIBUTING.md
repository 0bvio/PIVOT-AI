Contributing & sensitive-file policy

This repository intentionally excludes large model files, runtime caches, and private keys via the .gitignore at the repository root.

If you accidentally commit a large file or a secret, follow these steps to remove it from the Git history and index:

1) Remove the file from the index but keep it on disk:

```sh
git rm --cached path/to/large-or-secret.file
git commit -m "chore: remove sensitive/large file from index"
```

2) If you need to scrub the file from history (only if it was pushed to a remote), use the BFG or git filter-repo tool. Example with git filter-repo (recommended):

```sh
# Install: pip install git-filter-repo
git filter-repo --path path/to/large-or-secret.file --invert-paths
# Then force push to remote (coordinate with your team)
git push --force --all
```

3) Rotate any secrets that were exposed (private keys, tokens). Treat them as compromised.

4) If you prefer the BFG tool:

```sh
# Using the BFG to remove files by name or pattern
bfg --delete-files "*.safetensors" --delete-files "client_privatekey"
# then follow with
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push --force
```

Notes:
- Do NOT force-push unless you understand the implications for other contributors.
- Keep private keys out of the repository and store them in a secure secret manager or the filesystem outside of the repo.

