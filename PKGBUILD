# Maintainer: John Peter <johnpetersa19@gmail.com>

pkgname=paru-gui
pkgver=2.7.0
pkgrel=1
pkgdesc="A graphical user interface to manage AUR packages with ease and security"
arch=('any')
url="https://github.com/johnpetersa19/Paru_Gui"
license=('GPL3')

depends=(
    'python>=3.8'
    'python-requests>=2.25.0'
    'python-gobject>=3.42.0'
    'gtk4>=4.0.0'
    'libadwaita>=1.0.0'
    'glib2>=2.66.0'
    'paru>=1.11.0'
    'bubblewrap'
    'dbus'
    'glibc'
)
makedepends=(
    'meson>=1.0.0'
    'ninja'
    'python-setuptools>=65.0'
    'python-build'
    'python-wheel'
    'appstream-glib'
    'desktop-file-utils'
    'glib2-devel'
)
checkdepends=(
    'appstream-glib'
    'desktop-file-utils'
)
optdepends=(
    'python-pytest: for running tests'
    'python-black: for code formatting'
    'python-mypy: for type checking'
)

source=("$pkgname-$pkgver.tar.gz::https://github.com/johnpetersa19/Paru_Gui/archive/v$pkgver.tar.gz")
sha256sums=('PLACEHOLDER_CHECKSUM_MUST_BE_GENERATED')

prepare() {
    cd "Paru_Gui-$pkgver"
}

build() {
    arch-meson "Paru_Gui-$pkgver" build --prefix=/usr
    meson compile -C build
}

check() {
    meson test -C build --print-errorlogs
}

package() {
    DESTDIR="$pkgdir" meson install -C build
    install -Dm644 "Paru_Gui-$pkgver/COPYING" "$pkgdir/usr/share/licenses/$pkgname/COPYING"
    install -Dm644 "Paru_Gui-$pkgver/README.md" "$pkgdir/usr/share/doc/$pkgname/README.md"
}