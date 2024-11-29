use std::process::Command;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let sysroot = Command::new("rustc")
        .arg("--print")
        .arg("sysroot")
        .output()
        .expect("Failed to get rustc sysroot")
        .stdout;
    let sysroot = String::from_utf8_lossy(&sysroot).trim().to_string();

    println!("cargo:rustc-link-arg=-Wl,-rpath,{}/lib", sysroot);
    tonic_build::compile_protos("../proto/dataflow/v1/dataflow.proto")?;
    Ok(())
}