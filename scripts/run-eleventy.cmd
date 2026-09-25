@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

if defined npm_node_execpath (
  set "NODE_EXE=%npm_node_execpath%"
) else if exist "%ProgramFiles%\nodejs\node.exe" (
  set "NODE_EXE=%ProgramFiles%\nodejs\node.exe"
) else (
  set "NODE_EXE=node"
)

"%NODE_EXE%" "%PROJECT_DIR%\node_modules\@11ty\eleventy\cmd.cjs" %*
