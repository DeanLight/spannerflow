use std::collections::HashMap;
use std::sync::Mutex;


use libloading::{Library, Symbol};

use tonic::{transport::Server, Request, Response, Status};
use tokio_stream::iter;

use dataflow::dataflow_service_server::{DataflowService, DataflowServiceServer};
use dataflow::ie_function_service_client::IeFunctionServiceClient;
use dataflow::{*};


pub mod dataflow {
    tonic::include_proto!("dataflow.v1");
}

lazy_static::lazy_static! {
    // TODO: use real data structure
    static ref COLLECTIONS: Mutex<HashMap<String, Vec<u64>>> = Mutex::new(HashMap::new());
}

#[derive(Debug, Default)]
pub struct MyDataflowService {}

#[tonic::async_trait]
impl DataflowService for MyDataflowService {
    
    type GetCollectionStream = tokio_stream::Iter<std::vec::IntoIter<Result<GetCollectionResponse, tonic::Status>>>;

    async fn get_collection(
        &self,
        request: Request<GetCollectionRequest>,
    ) -> Result<Response<Self::GetCollectionStream>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();

        let collections = COLLECTIONS.lock().unwrap();

        if let Some(vec) = collections.get(&req.collection_name) {
            // Create a vector of GetCollectionResponse
            let responses: Vec<Result<GetCollectionResponse, Status>> = vec.iter().cloned().map(|row| {
                Ok(GetCollectionResponse { row: row.to_string() }) // Wrap in Ok
            }).collect();

            // Create a stream from the vector items
            let stream = iter(responses);

            // Return the stream in the response
            let response_stream = tonic::Response::new(stream);
            Ok(response_stream)
        } else {
            Err(Status::not_found("Collection not found"))
        }
    }

    async fn get_collections(
        &self,
        request: Request<()>,
    ) -> Result<Response<GetCollectionsResponse>, Status> {
        println!("Got a request: {:?}", request);
        let collections = COLLECTIONS.lock().unwrap();
        let collection_names: Vec<String> = collections.keys().cloned().collect();
        let reply = GetCollectionsResponse {
            collection_names,
        };

        Ok(Response::new(reply))
    }

    async fn add_row(
        &self,
        request: Request<AddRowRequest>,
    ) -> Result<Response<()>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();
        let mut collections = COLLECTIONS.lock().unwrap();

        if !collections.contains_key(&req.collection_name) {
            return Err(Status::not_found("Collection not found"));
        }
        if let Some(vec) = collections.get_mut(&req.collection_name) {
            // TODO: insert real value
            vec.push(vec.len() as u64);
        };
        let reply: () = ();

        Ok(Response::new(reply))
    }

    async fn delete_row(
        &self,
        request: Request<DeleteRowRequest>,
    ) -> Result<Response<()>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner(); 

        let mut collections = COLLECTIONS.lock().unwrap();

        if !collections.contains_key(&req.collection_name) {
            return Err(Status::not_found("Collection not found"));
        }
        if let Some(vec) = collections.get_mut(&req.collection_name) {
            // TODO: remove real value
            vec.pop();
        }

        let reply: () = ();

        Ok(Response::new(reply))
    }

    async fn add_collection(
        &self,
        request: Request<AddCollectionRequest>,
    ) -> Result<Response<()>, Status> {
        println!("Got a request: {:?}", request);

        let reply: () = ();
        let req = request.into_inner();
        
        let mut collections = COLLECTIONS.lock().unwrap();
        if collections.contains_key(&req.collection_name) {
            return Err(Status::already_exists("Collection already exists"));
        }
        collections.insert(req.collection_name, vec![]);

        Ok(Response::new(reply))
    }

    async fn delete_collection(
        &self,
        request: Request<DeleteCollectionRequest>,
    ) -> Result<Response<()>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();
        
        let mut collections = COLLECTIONS.lock().unwrap();
        if !collections.contains_key(&req.collection_name) {
            return Err(Status::not_found("Collection not found"));
        }
        collections.remove(req.collection_name.as_str());

        let reply: () = ();

        Ok(Response::new(reply))
    }

    async fn run_dataflow(
        &self,
        request: Request<RunDataflowRequest>,
    ) -> Result<Response<()>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();
        let mut collections = COLLECTIONS.lock().unwrap();
        
        if !collections.contains_key(&req.input_collection_name) {
            return Err(Status::not_found("Collection not found"));
        }
        let collection = collections.get_mut(&req.input_collection_name).unwrap();
        run_dataflow_so(req.so_path, req.fn_name, collection);
        let reply: () = ();

        Ok(Response::new(reply))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr = "127.0.0.1:50051".parse()?;
    let dataflow = MyDataflowService::default();

    Server::builder()
        .add_service(DataflowServiceServer::new(dataflow))
        .serve(addr)
        .await?;

    Ok(())
}

fn run_dataflow_so(so_path: String, fn_name: String, collection: &mut Vec<u64>) {
    // Load and use the shared library
    unsafe {
        let lib = Library::new(so_path).unwrap();
        let function: Symbol<unsafe extern "C" fn(&mut Vec<u64>)> = lib.get(fn_name.as_bytes()).unwrap();

        function(collection);
        println!("Output: {:?}", collection);
        
        // Explicitly unload the library
        std::mem::drop(lib);
    }

    println!("Shared library unloaded explicitly.");
}

pub async fn run_ie_function(
    server_address: String,
    function_name: String,
    collection_name: String,
) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    // Create a gRPC client
    let mut client = IeFunctionServiceClient::connect(server_address).await?;

    // Create the request
    let request = RunIeFunctionRequest {
        function_name,
        collection_name,
    };

    // Call the RunIEFunction RPC method
    let response = client.run_ie_function(Request::new(request)).await?;

    // Collect the streamed responses
    let mut results = Vec::new();
    let mut response_stream = response.into_inner();
    
    while let Some(response) = response_stream.message().await? {
        results.push(response.row); // Extract the row from the response
    }

    Ok(results)
}
