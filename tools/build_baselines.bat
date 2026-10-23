@echo off
rem ===========================================================================
rem  build_baselines.bat -- build Jiaoyang Li's official MAPF baselines with
rem  MSVC 2019 x64 (plain cl, no CMake):
rem      third_party\EECBS      ->  build\eecbs.exe
rem      third_party\MAPF-LNS2  ->  build\lns.exe
rem      third_party\PBS        ->  build\pbs.exe
rem
rem  * Boost.Program_options is compiled from source (there are no prebuilt
rem    Boost libs) into build\obj_boost_po and linked into each executable;
rem    Boost auto-linking is disabled with BOOST_ALL_NO_LIB.
rem  * tools\msvc_compat.h is force-included (/FI) into every solver source
rem    (missing std includes, iso646 tokens, glibc-identical rand()).
rem  * tools\include_shim provides <eigen3/Eigen/Core> for MAPF-LNS2's PIBT.
rem  * All portability changes are documented in third_party\PATCHES.md.
rem
rem  Usage:  tools\build_baselines.bat [eecbs] [lns] [pbs]   (default: all)
rem ===========================================================================
setlocal EnableExtensions

for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "TP=%ROOT%\third_party"
set "BOOST=%TP%\deps\boost_1_83_0"
set "EIGEN=%TP%\deps\eigen-3.4.0"
set "OUT=%ROOT%\build"
set "COMPAT=%ROOT%\tools\msvc_compat.h"
set "SHIM=%ROOT%\tools\include_shim"

if not defined VCToolsInstallDir (
    rem vcvars64.bat runs vswhere.exe from PATH; the VS Installer dir is not always on it
    if exist "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe" set "PATH=%PATH%;C:\Program Files (x86)\Microsoft Visual Studio\Installer"
    call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
)
where cl.exe >nul 2>nul
if errorlevel 1 (
    echo [build] ERROR: cl.exe not found - is MSVC 2019 Build Tools installed?
    exit /b 1
)

set "CXXFLAGS=/nologo /O2 /Ob2 /Oi /GL /DNDEBUG /EHsc /std:c++14 /MP /W1 /bigobj /DBOOST_ALL_NO_LIB /DNOMINMAX"
set "LDFLAGS=/LTCG /STACK:268435456"

set "TARGETS=%*"
if "%TARGETS%"=="" set "TARGETS=eecbs lns pbs"

if not exist "%OUT%" mkdir "%OUT%"

rem ---- Boost.Program_options (compiled once, linked into every exe) ---------
echo.
echo [build] ===== boost program_options =====
set "O=%OUT%\obj_boost_po"
if not exist "%O%" mkdir "%O%"
del /q "%O%\*.obj" 2>nul
cl /c %CXXFLAGS% /I"%BOOST%" /Fo"%O%\\" "%BOOST%\libs\program_options\src\*.cpp"
if errorlevel 1 goto :fail

for %%T in (%TARGETS%) do (
    call :build_%%T
    if errorlevel 1 goto :fail
)
echo.
echo [build] SUCCESS: %TARGETS%
exit /b 0

:fail
echo.
echo [build] FAILED
exit /b 1

rem ---------------------------------------------------------------- EECBS ---
:build_eecbs
echo.
echo [build] ===== EECBS =====
set "R=%TP%\EECBS"
set "O=%OUT%\obj_eecbs"
if not exist "%O%" mkdir "%O%"
del /q "%O%\*.obj" 2>nul
cl /c %CXXFLAGS% /FI"%COMPAT%" /I"%R%\inc" /I"%BOOST%" /Fo"%O%\\" "%R%\src\*.cpp"
if errorlevel 1 exit /b 1
cl /nologo "%O%\*.obj" "%OUT%\obj_boost_po\*.obj" /Fe"%OUT%\eecbs.exe" /link %LDFLAGS%
if errorlevel 1 exit /b 1
exit /b 0

rem ------------------------------------------------------------ MAPF-LNS2 ---
:build_lns
echo.
echo [build] ===== MAPF-LNS2 =====
set "R=%TP%\MAPF-LNS2"
set "O=%OUT%\obj_lns"
set "INC=/I"%R%\inc" /I"%R%\inc\CBS" /I"%R%\inc\PIBT" /I"%SHIM%" /I"%EIGEN%" /I"%BOOST%""
if not exist "%O%\CBS" mkdir "%O%\CBS"
if not exist "%O%\PIBT" mkdir "%O%\PIBT"
del /q "%O%\*.obj" "%O%\CBS\*.obj" "%O%\PIBT\*.obj" 2>nul
cl /c %CXXFLAGS% /FI"%COMPAT%" %INC% /Fo"%O%\\" "%R%\src\*.cpp"
if errorlevel 1 exit /b 1
cl /c %CXXFLAGS% /FI"%COMPAT%" %INC% /Fo"%O%\CBS\\" "%R%\src\CBS\*.cpp"
if errorlevel 1 exit /b 1
cl /c %CXXFLAGS% /FI"%COMPAT%" %INC% /Fo"%O%\PIBT\\" "%R%\src\PIBT\*.cpp"
if errorlevel 1 exit /b 1
cl /nologo "%O%\*.obj" "%O%\CBS\*.obj" "%O%\PIBT\*.obj" "%OUT%\obj_boost_po\*.obj" /Fe"%OUT%\lns.exe" /link %LDFLAGS%
if errorlevel 1 exit /b 1
exit /b 0

rem ------------------------------------------------------------------ PBS ---
:build_pbs
echo.
echo [build] ===== PBS =====
set "R=%TP%\PBS"
set "O=%OUT%\obj_pbs"
if not exist "%O%" mkdir "%O%"
del /q "%O%\*.obj" 2>nul
cl /c %CXXFLAGS% /FI"%COMPAT%" /I"%R%\inc" /I"%BOOST%" /Fo"%O%\\" "%R%\src\*.cpp"
if errorlevel 1 exit /b 1
cl /nologo "%O%\*.obj" "%OUT%\obj_boost_po\*.obj" /Fe"%OUT%\pbs.exe" /link %LDFLAGS%
if errorlevel 1 exit /b 1
exit /b 0
