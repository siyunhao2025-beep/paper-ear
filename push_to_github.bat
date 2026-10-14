@echo off
git init
git branch -M main
git add .gitignore SKILL.md README.md LICENSE requirements.txt agents/ references/ assets/ scripts/ examples/
git commit -m "feat: update paper-ear skill"
git remote remove origin 2>nul
git remote add origin https://github.com/siyunhao2025-beep/paper-ear.git
git push -u origin main
echo Successfully pushed paper-ear to https://github.com/siyunhao2025-beep/paper-ear
pause
