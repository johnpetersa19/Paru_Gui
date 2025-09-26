pkgname=paru-gui
pkgver=2.7.0
pkgrel=1
pkgdesc="Manage AUR packages with ease and security"
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
source=("${pkgname}-${pkgver}.tar.gz::https://github.com/johnpetersa19/Paru_Gui/archive/v${pkgver}.tar.gz")
sha256sums=('SKIP')
validpgpkeys=()

prepare() {
    cd "Paru_Gui-${pkgver}"
}

build() {
    cd "Paru_Gui-${pkgver}"
    arch-meson . build \
        --prefix=/usr \
        --libexecdir=lib \
        --sbindir=bin \
        --buildtype=plain \
        --wrap-mode=nodownload \
        -D b_lto=true \
        -D b_pie=true
    meson compile -C build
}

check() {
    cd "Paru_Gui-${pkgver}"
    meson test -C build --print-errorlogs
}

package() {
    cd "Paru_Gui-${pkgver}"
    meson install -C build --destdir="${pkgdir}"

    install -Dm644 COPYING "${pkgdir}/usr/share/licenses/${pkgname}/COPYING"
    install -Dm644 README.md "${pkgdir}/usr/share/doc/${pkgname}/README.md"
}
