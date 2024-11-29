fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("cargo:rustc-link-search=all=/Users/ofer/code/technion/spannerflow/rust_server/target/debug/deps");
    tonic_build::compile_protos("../proto/dataflow/v1/dataflow.proto")?;
    Ok(())
}