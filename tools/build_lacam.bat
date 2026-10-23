@echo off
rem Builds our LaCAM / LaCAM* / PIBT re-implementation with MSVC (x64, release).
rem Usage: tools\build_lacam.bat [exe name]   (default: mapf_lacam.exe)
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set ROOT=%~dp0..
set EXE=%~1
if "%EXE%"=="" set EXE=mapf_lacam.exe
if not exist "%ROOT%\build\obj_%~n1lacam" mkdir "%ROOT%\build\obj_%~n1lacam"
cl /nologo /O2 /Ob2 /Oi /GL /DNDEBUG /EHsc /std:c++17 /W3 /MP ^
   /Fo"%ROOT%\build\obj_%~n1lacam\\" /Fe"%ROOT%\build\%EXE%" ^
   "%ROOT%\src\*.cpp" /link /LTCG /STACK:268435456 || exit /b 1
echo built %ROOT%\build\%EXE%
