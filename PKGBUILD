# Maintainer: John Peter <johnpetersa19@gmail.com>

pkgname=paru-gui
pkgver=0.1.0
pkgrel=1
pkgdesc="A graphical user interface to manage AUR packages with ease and security"
arch=('x86_64' 'aarch64')
url="https://github.com/johnpetersa19/Paru_Gui"
license=('GPL3')

depends=(
    'gtk4>=4.0.0'
    'libadwaita>=1.6.0'
    'glib2>=2.66.0'
    'paru>=1.11.0'
    'bubblewrap'
    'dbus'
    'glibc'
    'gcc-libs'
    'openssl'
    'sqlite'
)
makedepends=(
    'meson>=1.0.0'
    'ninja'
    'rust'
    'cargo'
    'appstream-glib'
    'desktop-file-utils'
    'glib2-devel'
)
checkdepends=(
    'appstream-glib'
    'desktop-file-utils'
)

source=("https://github.com/johnpetersa19/Paru_Gui/archive/v$pkgver.tar.gz")
sha256sums=('SKIP')

prepare() {
    cd "Paru_Gui-$pkgver"
}

build() {
    cd "Paru_Gui-$pkgver"
    arch-meson . build --prefix=/usr
    meson compile -C build
}

check() {
    cd "Paru_Gui-$pkgver"
    meson test -C build --print-errorlogs
}

package() {
    cd "Paru_Gui-$pkgver"
    DESTDIR="$pkgdir" meson install -C build
    install -Dm644 "COPYING" "$pkgdir/usr/share/licenses/$pkgname/COPYING"
    install -Dm644 "README.md" "$pkgdir/usr/share/doc/$pkgname/README.md"
}