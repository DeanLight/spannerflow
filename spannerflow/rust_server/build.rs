fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("cargo:rustc-link-arg=-rdynamic");
    tonic_build::compile_protos("../proto/dataflow/v1/dataflow.proto")?;
    Ok(())
}