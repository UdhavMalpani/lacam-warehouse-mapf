@echo off
rem Builds the *official* LaCAM (AAAI-23) and LaCAM* (lacam2, IJCAI-23) code with MSVC.
rem They are used only to validate our re-implementation, not as baselines.
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set ROOT=%~dp0..
set TP=%ROOT%\third_party
set FLAGS=/nologo /O2 /Ob2 /Oi /GL /DNDEBUG /EHsc /std:c++17 /W1 /MP /bigobj /DNOMINMAX /FI"%ROOT%\tools\uint_compat.h"

if not exist "%ROOT%\build\obj_lacam_official" mkdir "%ROOT%\build\obj_lacam_official"
cl %FLAGS% /I"%TP%\lacam\lacam\include" /I"%TP%\lacam\third_party\argparse\include" ^
   /Fo"%ROOT%\build\obj_lacam_official\\" /Fe"%ROOT%\build\lacam_official.exe" ^
   "%TP%\lacam\main.cpp" "%TP%\lacam\lacam\src\*.cpp" /link /LTCG /STACK:268435456 || exit /b 1

if not exist "%ROOT%\build\obj_lacam2_official" mkdir "%ROOT%\build\obj_lacam2_official"
cl %FLAGS% /I"%TP%\lacam2\lacam2\include" /I"%TP%\lacam2\third_party\argparse\include" ^
   /Fo"%ROOT%\build\obj_lacam2_official\\" /Fe"%ROOT%\build\lacam2_official.exe" ^
   "%TP%\lacam2\main.cpp" "%TP%\lacam2\lacam2\src\*.cpp" /link /LTCG /STACK:268435456 || exit /b 1
echo built official lacam / lacam2
