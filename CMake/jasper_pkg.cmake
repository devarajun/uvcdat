set(JASPER_MAJOR 1)
set(JASPER_MINOR 900)
set(JASPER_PATCH 1)
set(JASPER_VERSION ${JASPER_MAJOR}.${JASPER_MINOR}.${JASPER_PATCH})
set(JASPER_URL ${LLNL_URL})
set(JASPER_GZ jasper-${JASPER_VERSION}.tgz)
set(JASPER_MD5 b5ae85050d034555790a3ccbc2522860)

add_cdat_package(jasper "" "" "" "")
set(jasper_deps ${pkgconfig_pkg} ${jpeg_pkg} ${zlib_pkg})

