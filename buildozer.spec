[app]
title = SiteChecker
package.name = sitechecker
package.domain = org.sitechecker
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy,android,certifi,urllib3
orientation = portrait
fullscreen = 0
android.permissions = android.permission.INTERNET, android.permission.ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 0
