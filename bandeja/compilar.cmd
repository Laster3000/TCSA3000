@echo off
rem Compila TCSA3000.exe (bandeja sin consola) en la raiz de TCSA3000 con el csc de .NET Framework 4 incluido en Windows.
setlocal
set "AQUI=%~dp0"
set "RAIZ=%AQUI%.."
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
"%CSC%" /nologo /target:winexe /optimize+ /out:"%RAIZ%\TCSA3000.exe" /r:System.Web.Extensions.dll /r:System.Windows.Forms.dll /r:System.Drawing.dll "%AQUI%TCSA3000Bandeja.cs"
exit /b %ERRORLEVEL%
