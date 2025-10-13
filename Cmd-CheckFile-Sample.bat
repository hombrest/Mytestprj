
setlocal enabledelayedexpansion

:: Path to your checksum list
set "checksumFile=checksums.txt"

for /f "usebackq tokens=1,2*" %%A in ("%checksumFile%") do (
    set "expectedChecksum=%%A"
    set "filePath=%%B"

    rem Check if file exists
    if exist "!filePath!" (
        rem Compute actual checksum
        for /f "usebackq tokens=1" %%C in (`certutil -hashfile "!filePath!" MD5 ^| find /i "MD5"`) do (
            set "actualChecksum=%%C"
            rem Remove spaces
            for %%D in (!actualChecksum!) do set "actualChecksum=%%D"
        )

        rem Compare checksums
        if /i "!actualChecksum!"=="!expectedChecksum!" (
            echo [OK] !filePath!
        ) else (
            echo [FAIL] !filePath! (Expected: !expectedChecksum!, Got: !actualChecksum!)
        )
    ) else (
        echo [NOT FOUND] !filePath!
    )
)

pause
