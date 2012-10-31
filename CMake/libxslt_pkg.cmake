set(XSLT_MAJOR 1)
set(XSLT_MINOR 1)
set(XSLT_PATCH 22)
set(XSLT_MAJOR_SRC 1)
set(XSLT_MINOR_SRC 1)
set(XSLT_PATCH_SRC 26)
set(XSLT_URL ${LLNL_URL})
set(XSLT_GZ libxslt-${XSLT_MAJOR_SRC}.${XSLT_MINOR_SRC}.${XSLT_PATCH_SRC}.tar.gz)
set(XSLT_MD5 e61d0364a30146aaa3001296f853b2b9)

add_cdat_package(libXSLT "" "" "" "")
set(libXSLT_deps ${pkgconfig_pkg} ${readline_pkg} ${libXML2_pkg})

