Write-Host "Cleaning git cache for ignored files..."

$paths = @(
    "backups",
    "*.db",
    "dist",
    "build",
    "*.spec"
)

foreach ($p in $paths) {
    try {
        git rm -r --cached $p
        Write-Host "Removed from cache: $p"
    }
    catch {
        Write-Host "Nothing to remove for: $p"
    }
}

git add .gitignore
git commit -m "gitignore cleanup: stop tracking db/backups/builds"
git push

Write-Host "Done! ✅"
