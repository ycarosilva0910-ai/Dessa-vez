[app]

title = Derrote o Gordo do Pai do Kayk
package.name = derroteogordo
package.domain = com.ycaro

source.dir = .
source.include_exts = py,png,jpg,jpeg,webp,ogg,wav,mp3,ttf,json

version = 0.1
requirements = python3,pygame

orientation = landscape
fullscreen = 1

android.api = 36
android.minapi = 24
android.ndk = 29
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

p4a.bootstrap = sdl2
p4a.branch = develop

[buildozer]

log_level = 2
warn_on_root = 1
