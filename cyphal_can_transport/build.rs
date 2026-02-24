fn main() {
    cxx_build::bridge("src/lib.rs")
        .include("include") // cyphal_callback.hpp の宣言を CXX 型チェックに提供
        .compile("cyphal_can_transport");

    println!("cargo:rerun-if-changed=src/lib.rs");
    println!("cargo:rerun-if-changed=include/cyphal_callback.hpp");
}
