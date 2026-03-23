@echo off
REM Koda Digest Auto-Deploy for Windows
REM Runs daily via Task Scheduler to push digest updates to GitHub/Vercel
REM Setup: Task Scheduler > Create Task > Trigger: Daily at desired time
REM        Action: Start Program > Browse to this .bat file

cd /d "C:\Users\arno_\Digest"

REM Stage all HTML files and config
git add morning-briefing-koda.html morning-briefing-koda-*.html manifest.json search-index.json index.html vercel.json .gitignore 2>nul

REM Check if there are changes to commit
git diff --cached --quiet
if %ERRORLEVEL%==0 (
    echo No new changes to deploy.
    exit /b 0
)

REM Commit with today's date
for /f "tokens=1-3 delims=/" %%a in ('echo %date%') do (
    set DATESTR=%%c-%%a-%%b
)
REM Fallback: use PowerShell for reliable date formatting
for /f %%i in ('powershell -command "Get-Date -Format yyyy-MM-dd"') do set DATESTR=%%i

git commit -m "Digest %DATESTR%"

REM Push to GitHub (Vercel auto-deploys within ~30 seconds)
git push origin main

echo Deployed! Vercel will auto-build in ~30 seconds.
