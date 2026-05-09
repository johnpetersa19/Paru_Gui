fn main() {
    glib_build_tools::compile_resources(
        &["src"],
        "src/paru-gui.gresource.xml",
        "paru-gui.gresource",
    );
}
