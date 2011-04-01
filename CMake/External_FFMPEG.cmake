# The FFMPEG external project for ParaView

set(ffmpeg_source "${CMAKE_CURRENT_BINARY_DIR}/FFMPEG")
set(ffmpeg_install "${CMAKE_CURRENT_BINARY_DIR}/FFMPEG-install")

configure_file(${cdat_CMAKE_SOURCE_DIR}/ffmpeg_configure_step.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/ffmpeg_configure_step.cmake
    @ONLY)

ExternalProject_Add(FFMPEG
  DOWNLOAD_DIR ${CMAKE_CURRENT_BINARY_DIR}
  SOURCE_DIR ${ffmpeg_source}
  INSTALL_DIR ${ffmpeg_install}
  URL ${FFMPEG_URL}/${FFMPEG_GZ}
  URL_MD5 ${FFMPEG_MD5}
  BUILD_IN_SOURCE 1
  PATCH_COMMAND ""
  CONFIGURE_COMMAND ${CMAKE_COMMAND} -P ${CMAKE_CURRENT_BINARY_DIR}/ffmpeg_configure_step.cmake
  DEPENDS ${FFMPEG_DEPENDENCIES}
  )

set(FFMPEG_INCLUDE_DIR ${ffmpeg_install}/include)
set(FFMPEG_avcodec_LIBRARY ${ffmpeg_install}/lib/libavcodec${_LINK_LIBRARY_SUFFIX})
set(FFMPEG_avformat_LIBRARY ${ffmpeg_install}/lib/libavformat${_LINK_LIBRARY_SUFFIX})
set(FFMPEG_avutil_LIBRARY ${ffmpeg_install}/lib/libavutil${_LINK_LIBRARY_SUFFIX})
set(FFMPEG_swscale_LIBRARY ${ffmpeg_install}/lib/libswscale${_LINK_LIBRARY_SUFFIX})
