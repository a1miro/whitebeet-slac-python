cmake_minimum_required(VERSION 3.14.7)

project(whitebeet-slac-python
    VERSION 0.1.0
    DESCRIPTION "WhiteBeet SLAC module for EVerest - Python implementation"
    LANGUAGES NONE
)

include(GNUInstallDirs)

# Install Python module
install(
    DIRECTORY modules/WhiteBeetSlac
    DESTINATION ${CMAKE_INSTALL_LIBEXECDIR}/everest/modules
    FILES_MATCHING 
    PATTERN "*.py"
    PATTERN "*.yaml"
)

# Make the Python module executable
install(
    FILES modules/WhiteBeetSlac/module.py
    DESTINATION ${CMAKE_INSTALL_LIBEXECDIR}/everest/modules/WhiteBeetSlac
    PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
)

# Install configuration files
install(
    FILES 
        config/config-basic.yaml
        config/config-full.yaml
    DESTINATION ${CMAKE_INSTALL_SYSCONFDIR}/everest
)

# CPack configuration for packaging
set(CPACK_PACKAGE_NAME "whitebeet-slac-python")
set(CPACK_PACKAGE_VENDOR "Parallel Dynamic Ltd.")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "WhiteBeet SLAC module for EVerest (Python)")
set(CPACK_PACKAGE_VERSION_MAJOR ${PROJECT_VERSION_MAJOR})
set(CPACK_PACKAGE_VERSION_MINOR ${PROJECT_VERSION_MINOR})
set(CPACK_PACKAGE_VERSION_PATCH ${PROJECT_VERSION_PATCH})
set(CPACK_GENERATOR "DEB;TGZ")
set(CPACK_DEBIAN_PACKAGE_MAINTAINER "Andrei Mironenko <amironenko@paralleldynamic.com>")
set(CPACK_DEBIAN_PACKAGE_DEPENDS "python3 (>= 3.6), python3-scapy, python3-pip")
set(CPACK_DEBIAN_PACKAGE_SECTION "net")

include(CPack)

# Print installation summary
message(STATUS "")
message(STATUS "WhiteBeet SLAC Python Module Configuration:")
message(STATUS "  Version: ${PROJECT_VERSION}")
message(STATUS "  Install prefix: ${CMAKE_INSTALL_PREFIX}")
message(STATUS "  Module directory: ${CMAKE_INSTALL_LIBEXECDIR}/everest/modules")
message(STATUS "  Config directory: ${CMAKE_INSTALL_SYSCONFDIR}/everest")
message(STATUS "")
