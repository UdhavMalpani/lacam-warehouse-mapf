@echo off
rem Recreates third_party\ at the exact commits used for the benchmark.
rem Needs git and tar on PATH (both ship with Windows 10+ / Git for Windows).
rem Afterwards: tools\build_baselines.bat and tools\build_official_lacam.bat
setlocal
set ROOT=%~dp0..
set TP=%ROOT%\third_party
cd /d "%TP%" || exit /b 1

call :clone EECBS     https://github.com/Jiaoyang-Li/EECBS.git     06ec70585dc4ad73177580a4ef91138335fd4d24 || exit /b 1
call :clone MAPF-LNS2 https://github.com/Jiaoyang-Li/MAPF-LNS2.git 1369823985a15944f9a339226d521f61605a6d17 || exit /b 1
call :clone PBS       https://github.com/Jiaoyang-Li/PBS.git       d7b91fa5abdbb1376e8fc2cffa995a84eac811df || exit /b 1
call :clone lacam     https://github.com/Kei18/lacam.git           0a679a1b4ed0a7ff9a0d400ed72635ec31253f7b || exit /b 1
call :clone lacam2    https://github.com/Kei18/lacam2.git          61a4c40ce91ce18c06eb2fe070aa9f1951eecb8d || exit /b 1
call :clone pibt2     https://github.com/Kei18/pibt2.git           faab5b916649549f1cd563df8dbf6e4f6382f631 || exit /b 1

rem MSVC patches for the official LaCAM code (see PATCHES.md); the baselines stay unmodified
git -C lacam  apply "%TP%\patches\lacam.patch"  || exit /b 1
git -C lacam2 apply "%TP%\patches\lacam2.patch" || exit /b 1

if not exist deps mkdir deps
if not exist _downloads mkdir _downloads
if not exist deps\boost_1_83_0 (
  curl -L -o _downloads\boost_1_83_0.tar.gz https://archives.boost.io/release/1.83.0/source/boost_1_83_0.tar.gz || exit /b 1
  tar -xzf _downloads\boost_1_83_0.tar.gz -C deps || exit /b 1
)
if not exist deps\eigen-3.4.0 (
  curl -L -o _downloads\eigen-3.4.0.tar.gz https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.tar.gz || exit /b 1
  tar -xzf _downloads\eigen-3.4.0.tar.gz -C deps || exit /b 1
)
echo third_party ready
exit /b 0

:clone
if exist "%1" (echo %1 already present & exit /b 0)
git clone --recursive %2 %1 || exit /b 1
git -C %1 checkout %3 || exit /b 1
git -C %1 submodule update --init --recursive || exit /b 1
exit /b 0
