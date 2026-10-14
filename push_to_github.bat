@echo off
git init
git branch -M main
git add SKILL.md README.md requirements.txt assets/ scripts/ examples/
git commit -m "feat: upgrade paper-ear skill with visual showcase, demo video, GIF preview, and flagship README"
git remote remove origin 2>nul
git remote add origin https://github.com/siyunhao2025-beep/paper-ear.git
git push -u origin main
echo Successfully pushed paper-ear to https://github.com/siyunhao2025-beep/paper-ear
pause
