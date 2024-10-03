use std::collections::HashMap;
use std::sync::Mutex;
use csv;


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
    static ref COLLECTIONS: Mutex<HashMap<String, Vec<Vec<String>>>> = Mutex::new(HashMap::new());
}

#[derive(Debug, Default)]
pub struct MyDataflowService {}

#[tonic::async_trait]
impl DataflowService for MyDataflowService {
    
    type GetCollectionStream = tokio_stream::Iter<std::vec::IntoIter<Result<GetCollectionResponse, tonic::Status>>>;

    async fn save_to_csv(
        &self,
        request: Request<SaveToCsvRequest>,
    ) -> Result<Response<()>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();
        let collections = match COLLECTIONS.lock() {
            Ok(lock) => lock,
            Err(poisoned) => {
                eprintln!("Mutex was poisoned: {:?}", poisoned);
                poisoned.into_inner() // This will give you access to the inner data.
            }
        };
        if let Some(vec) = collections.get(&req.collection_name) {
            let mut wtr = csv::Writer::from_path(req.file_path).map_err(|e| {
                eprintln!("Failed to create CSV writer: {:?}", e);
                Status::internal("Failed to create CSV writer")
            })?;
            // TODO: write real header
            wtr.write_record(&["field1", "field2"]).map_err(|e| {
                eprintln!("Failed to write field to CSV: {:?}", e);
                Status::internal("Failed to write field to CSV")
            })?;
            for row in vec {
                wtr.write_record(row).map_err(|e| {
                    eprintln!("Failed to write record to CSV: {:?}", e);
                    Status::internal("Failed to write record to CSV")
                })?;
            }
            wtr.flush().map_err(|e| {
                eprintln!("Failed to flush CSV writer: {:?}", e);
                Status::internal("Failed to flush CSV writer")
            })?;
        } else {
            return Err(Status::not_found("Collection not found"));
        }

        let reply: () = ();
        Ok(Response::new(reply))
    }

    async fn load_from_csv(
        &self,
        request: Request<LoadFromCsvRequest>,
    ) -> Result<Response<()>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();
        let mut collections = match COLLECTIONS.lock() {
            Ok(lock) => lock,
            Err(poisoned) => {
                eprintln!("Mutex was poisoned: {:?}", poisoned);
                poisoned.into_inner() // This will give you access to the inner data.
            }
        };
        if collections.contains_key(&req.collection_name) {
            return Err(Status::already_exists("Collection already exists"));
        }
        let mut rdr = csv::Reader::from_path(req.file_path).map_err(|e| {
            eprintln!("Failed to create CSV reader: {:?}", e);
            Status::internal("Failed to create CSV reader")
        })?;
        let mut vec = Vec::new();
        for result in rdr.records() {
            let record = result.map_err(|e| {
                eprintln!("Failed to read record from CSV: {:?}", e);
                Status::internal("Failed to read record from CSV")
            })?;
            let row: Vec<String> = record.iter().map(|s| s.to_string()).collect();
            vec.push(row);
        }
        collections.insert(req.collection_name, vec);

        let reply: () = ();
        Ok(Response::new(reply))
    }   

    async fn get_collection(
        &self,
        request: Request<GetCollectionRequest>,
    ) -> Result<Response<Self::GetCollectionStream>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();

        let collections = match COLLECTIONS.lock() {
            Ok(lock) => lock,
            Err(poisoned) => {
                eprintln!("Mutex was poisoned: {:?}", poisoned);
                poisoned.into_inner() // This will give you access to the inner data.
            }
        };
        if let Some(vec) = collections.get(&req.collection_name) {
            // Create a vector of GetCollectionResponse
            let responses: Vec<Result<GetCollectionResponse, Status>> = vec.iter().cloned().map(|row| {
                Ok(GetCollectionResponse { row: row }) // Wrap in Ok
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
        let collections = match COLLECTIONS.lock() {
            Ok(lock) => lock,
            Err(poisoned) => {
                eprintln!("Mutex was poisoned: {:?}", poisoned);
                poisoned.into_inner() // This will give you access to the inner data.
            }
        };
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
        let mut collections = match COLLECTIONS.lock() {
            Ok(lock) => lock,
            Err(poisoned) => {
                eprintln!("Mutex was poisoned: {:?}", poisoned);
                poisoned.into_inner() // This will give you access to the inner data.
            }
        };

        if !collections.contains_key(&req.collection_name) {
            return Err(Status::not_found("Collection not found"));
        }
        if let Some(vec) = collections.get_mut(&req.collection_name) {
            vec.push(req.row);
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

        let mut collections = match COLLECTIONS.lock() {
            Ok(lock) => lock,
            Err(poisoned) => {
                eprintln!("Mutex was poisoned: {:?}", poisoned);
                poisoned.into_inner() // This will give you access to the inner data.
            }
        };

        if !collections.contains_key(&req.collection_name) {
            return Err(Status::not_found("Collection not found"));
        }
        if let Some(vec) = collections.get_mut(&req.collection_name) {
            if let Some(pos) = vec.iter().position(|x| *x == req.row) {
                vec.remove(pos);
            }
            else {
                return Err(Status::not_found("row not found"));
            }
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
        
        let mut collections = match COLLECTIONS.lock() {
            Ok(lock) => lock,
            Err(poisoned) => {
                eprintln!("Mutex was poisoned: {:?}", poisoned);
                poisoned.into_inner() // This will give you access to the inner data.
            }
        };
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
        
        let mut collections = match COLLECTIONS.lock() {
            Ok(lock) => lock,
            Err(poisoned) => {
                eprintln!("Mutex was poisoned: {:?}", poisoned);
                poisoned.into_inner() // This will give you access to the inner data.
            }
        };
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
        let mut collections = match COLLECTIONS.lock() {
            Ok(lock) => lock,
            Err(poisoned) => {
                eprintln!("Mutex was poisoned: {:?}", poisoned);
                poisoned.into_inner() // This will give you access to the inner data.
            }
        };

        if !collections.contains_key(&req.input_collection_name) {
            return Err(Status::not_found("Collection not found"));
        }
        let collection = collections.get_mut(&req.input_collection_name).unwrap();
        let result = run_dataflow_so(req.so_path, req.fn_name, collection);
        if let Err(status) = result {
            return Err(status); // Propagate the error back to the caller
        }

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

fn run_dataflow_so(so_path: String, fn_name: String, collection: &mut Vec<Vec<String>>) -> Result<(), Status> {
    // Load and use the shared library
    unsafe {
        let lib = Library::new(&so_path).map_err(|e| {
            eprintln!("Failed to load library from path {}: {:?}", so_path, e);
            Status::not_found("Failed to load shared library")
        })?;

        let function: Symbol<unsafe extern "C" fn(&mut Vec<Vec<String>>)> = lib.get(fn_name.as_bytes()).map_err(|e| {
            eprintln!("Failed to get function {}: {:?}", fn_name, e);
            Status::not_found("Failed to get function from library")
        })?;
        
        function(collection);
        std::mem::drop(lib);
    }
    println!("Output: {:?}", collection);
    
    // Explicitly unload the library

    println!("Shared library unloaded explicitly.");
    Ok(())
}

pub async fn run_ie_function(
    server_address: String,
    function_name: String,
    collection_name: String,
) -> Result<Vec<Vec<String>>, Box<dyn std::error::Error>> {
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
