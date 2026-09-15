@echo off
REM -- AERIS LIGHT - the load-free configuration -----------------------
REM The pairing measured in docs\AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md
REM ?6.7. Two switches, and they solve different halves of "AERIS is heavy":
REM
REM   AERIS_SPLIT_BRAIN=1  brain runs in its OWN child process, so this GUI
REM                        process holds no torch at all -> the 0xC0000374
REM                        heap-crash class is impossible here by construction.
REM   AERIS_LITE_ML=1      boot loads NO model weights. The tiered router
REM                        answers exact-match / arithmetic / anchor commands
REM                        with string work alone and pulls the encoder in
REM                        only when an utterance actually needs it.
REM
REM Measured together: brain ready ~1.9s, ~126 MB across both processes,
REM against ~15-20s and ~810 MB for the default eager single-process boot.
REM
REM The trade: the FIRST utterance that misses every cheap tier pays the
REM encoder load in one go (~10s). Ordinary command sessions never do.
REM
REM Debug console:  AERIS_LIGHT.bat debug
set KMP_DUPLICATE_LIB_OK=TRUE
set AERIS_SPLIT_BRAIN=1
set AERIS_LITE_ML=1
cd /d "%~dp0"
call "%~dp0_python.bat"
if /i "%1"=="debug" (
    "%AERIS_PY%" run_gui.py
) else (
    start "" "%AERIS_PYW%" run_gui.py
)
