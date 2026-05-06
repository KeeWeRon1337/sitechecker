[app]
title = SiteChecker
package.name = sitechecker
package.domain = org.sitechecker
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0

requirements = python3,kivy,certifi,urllib3

orientation = portrait
fullscreen = 0

android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE

android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

android.meta_data = android:usesCleartextTraffic=true

[buildozer]
log_level = 2
warn_on_root = 0
