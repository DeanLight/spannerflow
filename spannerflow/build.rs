fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::compile_protos("proto/dataflow/v1/dataflow.proto")?;
    Ok(())
}