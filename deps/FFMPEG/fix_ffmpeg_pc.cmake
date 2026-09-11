# Rewrite the prebuilt Windows FFmpeg .pc files' broken relative prefix
# (they ship `prefix=./dist`, `libdir=./dist/lib`, `includedir=./dist/include`)
# to the absolute install prefix, so pkg_check_modules(LIBAV) on Windows resolves
# real -L/-I paths. Invoked from FFMPEG.cmake's INSTALL_COMMAND with -DPCDIR/-DPCPREFIX.
file(GLOB _pcs "${PCDIR}/libav*.pc" "${PCDIR}/libsw*.pc" "${PCDIR}/libpostproc.pc")
foreach(_pc IN LISTS _pcs)
    file(READ "${_pc}" _c)
    string(REGEX REPLACE "prefix=[^\r\n]*"     "prefix=${PCPREFIX}"            _c "${_c}")
    string(REGEX REPLACE "libdir=[^\r\n]*"     "libdir=\${prefix}/lib"         _c "${_c}")
    string(REGEX REPLACE "includedir=[^\r\n]*" "includedir=\${prefix}/include" _c "${_c}")
    file(WRITE "${_pc}" "${_c}")
    message(STATUS "fix_ffmpeg_pc: rewrote prefix in ${_pc}")
endforeach()
