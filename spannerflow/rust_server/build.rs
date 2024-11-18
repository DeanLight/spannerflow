use std::process::Command;


fn main() -> Result<(), Box<dyn std::error::Error>> {
    let lib_path = "../rust_span";

    let output = Command::new("cargo")
        .arg("build")
        .arg("--release")
        .current_dir(lib_path)
        .output()
        .expect("Failed to build library");

    if !output.status.success() {
        panic!(
            "Library build failed:\n{}",
            String::from_utf8_lossy(&output.stderr)
        );
    }


    tonic_build::compile_protos("../proto/dataflow/v1/dataflow.proto")?;
    Ok(())
}