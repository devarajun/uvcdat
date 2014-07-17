set(PYCLIMATE_VERSION 1.2.3)
set(PYCLIMATE_URL ${LLNL_URL})
set(PYCLIMATE_GZ PyClimate-${PYCLIMATE_VERSION}.tar.gz)
set(PYCLIMATE_SOURCE ${PYCLIMATE_URL}/${PYCLIMATE_GZ})
set(PYCLIMATE_MD5 094ffd0adedc3ede24736e0c0ff1699f)

add_cdat_package_dependent(pyclimate "" "" OFF "CDAT_BUILD_LEAN" OFF)
