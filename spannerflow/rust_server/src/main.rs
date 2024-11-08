use std::collections::HashMap;
use std::sync;
use std::env;
use csv;


use libloading::{Library, Symbol};

use tonic::{transport::Server, Request, Response, Status};
use tokio::sync::Mutex;
use tokio_stream::iter;
use tokio_stream::StreamExt;

use dataflow::dataflow_service_server::{DataflowService, DataflowServiceServer};
use dataflow::{*};


pub mod dataflow {
    tonic::include_proto!("dataflow.v1");
}

lazy_static::lazy_static! {
    static ref COLLECTIONS: Mutex<HashMap<String, Vec<Vec<String>>>> = Mutex::new(HashMap::new());
    static ref SCHEMAS: Mutex<HashMap<String, Vec<dataflow::DataType>>> = Mutex::new(HashMap::new());
    static ref DOCUMENTS: sync::Mutex<HashMap<i32, String>> = sync::Mutex::new(HashMap::new());
}

#[no_mangle]
pub extern "C" fn add_document(id: i32, doc: String) {
    let mut documents = DOCUMENTS.lock().unwrap();
    documents.insert(id, doc);
}

#[no_mangle]
pub extern "C" fn delete_document(id: i32, doc: String) {
    let mut documents = DOCUMENTS.lock().unwrap();
    documents.remove(&id);
}

#[no_mangle]
pub extern "C" fn get_document(id: i32) -> String {
    let documents = DOCUMENTS.lock().unwrap();
    documents.get(&id).unwrap().clone()
}

#[derive(Debug, Default)]
pub struct MyDataflowService {}

fn validate_schema(schema: &Vec<dataflow::DataType>, row: &Vec<String>) -> bool {
    if schema.len() != row.len() {
        return false;
    }
    for (data_type, value) in schema.iter().zip(row.iter()) {
        match data_type {
            dataflow::DataType::Bool => {
                if value.parse::<bool>().is_err() {
                    return false;
                }
            }
            dataflow::DataType::Float => {
                if value.parse::<f64>().is_err() {
                    return false;
                }
            }
            dataflow::DataType::Int => {
                if value.parse::<i32>().is_err() {
                    return false;
                }
            }
            dataflow::DataType::Int64 => {
                if value.parse::<i64>().is_err() {
                    return false;
                }
            }
            dataflow::DataType::String => {
                if value.parse::<String>().is_err() {
                    return false;
                }
            }
            dataflow::DataType::Unspecified => {
                return false;
            }
            dataflow::DataType::Span => {
                // TODO: Implement Span validation
                return false;
            }
            dataflow::DataType::Custom => {
                return true;
            }
        }
    }
    true
}


#[tonic::async_trait]
impl DataflowService for MyDataflowService {
    
    type GetCollectionStream = tokio_stream::Iter<std::vec::IntoIter<Result<GetCollectionResponse, tonic::Status>>>;
    type RunDataflowStream = tokio_stream::Iter<std::vec::IntoIter<Result<RunDataflowResponse, tonic::Status>>>;
    
    async fn add_rows(
        &self,
        request: Request<tonic::Streaming<AddRowsRequest>>,
    ) -> Result<Response<()>, Status> {
        println!("Got a streaming request: {:?}", request);
        
        let mut stream = request.into_inner();  // Extract the stream
        let mut collection_name: Option<String> = None;
        let mut collections = COLLECTIONS.lock().await;
        
        let schemas = SCHEMAS.lock().await;
    
        // Process the stream
        while let Some(req) = stream.next().await {
            match req {
                Ok(message) => {
                    println!("Received message: {:?}", message); // Debug log
                    if let Some(collection) = message.message_type {
                        match collection {
                            // Handle the collection name variant
                            dataflow::add_rows_request::MessageType::CollectionName(name) => {
                                println!("Received collection name: {}", name); // Debug log
                                collection_name = Some(name);
                            }
                            // Handle the row variant
                            dataflow::add_rows_request::MessageType::Row(row) => {
                                println!("Received row: {:?}", row); // Debug log
                                if let Some(ref name) = collection_name {
                                    if let Some(coll) = collections.get_mut(name) {
                                        if validate_schema(schemas.get(name).unwrap(), &row.row) {
                                            coll.push(row.row.clone());
                                        } else {
                                            eprintln!("Invalid row schema for collection: {}", name);
                                            return Err(Status::invalid_argument("Invalid row schema"));
                                        }
                                    } else {
                                        eprintln!("Collection not found: {}", name);
                                        return Err(Status::not_found("Collection not found"));
                                    }
                                } else {
                                    eprintln!("Collection name not found");
                                    return Err(Status::invalid_argument("Collection name not found"));
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    eprintln!("Error receiving stream: {:?}", e);
                    return Err(Status::internal("Failed to receive stream"));
                }
            }
        }
        Ok(Response::new(()))
    }
    


    async fn save_to_csv(
        &self,
        request: Request<SaveToCsvRequest>,
    ) -> Result<Response<()>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();
        let mut delimiter = b',';
        if req.delimiter.len() > 1 {
            return Err(Status::invalid_argument("Delimiter must be a single character"));
        }
        else if req.delimiter.len() == 1 {
            delimiter = req.delimiter[0];
        }
        let collections = COLLECTIONS.lock().await;
        if let Some(vec) = collections.get(&req.collection_name) {
            let mut wtr = csv::WriterBuilder::new()
                .delimiter(delimiter)
                .from_path(req.file_path).map_err(|e| {
                    eprintln!("Failed to create CSV writer: {:?}", e);
                    Status::internal("Failed to create CSV writer")
                })?;
            if let Some(schema) = SCHEMAS.lock().await.get(&req.collection_name) {
                let mut csv_row = Vec::new();
                for data_type in schema {
                    csv_row.push(data_type.as_str_name());
                }
                wtr.write_record(csv_row).map_err(|e| {
                    eprintln!("Failed to write schema to CSV: {:?}", e);
                    Status::internal("Failed to write schema to CSV")
                })?;
            }
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
        let mut delimiter = b',';
        if req.delimiter.len() > 1 {
            return Err(Status::invalid_argument("Delimiter must be a single character"));
        }
        else if req.delimiter.len() == 1 {
            delimiter = req.delimiter[0];
        }
        let mut collections = COLLECTIONS.lock().await;
        let mut schemas = SCHEMAS.lock().await;
        if req.has_header && (collections.contains_key(&req.collection_name) || schemas.contains_key(&req.collection_name)) {
            return Err(Status::already_exists("Collection already exists"));
        }
        let mut rdr = csv::ReaderBuilder::new()
            .delimiter(delimiter)
            .from_path(req.file_path).map_err(|e| {
                eprintln!("Failed to create CSV reader: {:?}", e);
                Status::internal("Failed to create CSV reader")
            })?;
        let mut schema = Vec::new();
        if req.has_header {
            match rdr.headers() {
                Ok(header) => {
                    for field in header.iter() {
                        // Assuming dataflow::DataType::from_str_name returns an Option or Result
                        // Handle the unwrap safely if needed
                        if let Some(data_type) = dataflow::DataType::from_str_name(field) {
                            schema.push(data_type);
                        } else {
                            // Handle the case where from_str_name returns None
                            eprintln!("Unknown data type in header: {}", field);
                        }
                    }
                }
                Err(e) => {
                    eprintln!("Failed to read CSV headers: {}", e);
                    return Err(Status::internal("Failed to read CSV headers"));
                }
            }
            schemas.insert(req.collection_name.clone(), schema);
            collections.insert(req.collection_name.clone(), Vec::new());
        }

        let collection = collections.get_mut(&req.collection_name).unwrap();
        for result in rdr.records() {
            let record = result.map_err(|e| {
                eprintln!("Failed to read record from CSV: {:?}", e);
                Status::internal("Failed to read record from CSV")
            })?;
            let row: Vec<String> = record.iter().map(|s| s.to_string()).collect();
            collection.push(row);
        }

        let reply: () = ();
        Ok(Response::new(reply))
    }   

    async fn get_collection(
        &self,
        request: Request<GetCollectionRequest>,
    ) -> Result<Response<Self::GetCollectionStream>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();

        let collections = COLLECTIONS.lock().await;
        if let Some(vec) = collections.get(&req.collection_name) {
            let responses: Vec<Result<GetCollectionResponse, Status>> = vec.iter().cloned().map(|row| {
                Ok(GetCollectionResponse { row: row })
            }).collect();

            let stream = iter(responses);

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
    
        let collections = COLLECTIONS.lock().await;
        let mut response_collections: Vec<dataflow::Collection> = Vec::new();
        let schemas = SCHEMAS.lock().await;
        for (name, _schema) in collections.iter() {
            let schema_types: Vec<i32> = schemas.get(name)
            .map(|data_types| data_types.iter().map(|data_type| *data_type as i32).collect())
            .unwrap_or_default();
            
            let collection = dataflow::Collection {
                name: name.clone(),
                schema: schema_types,
            };
            
            response_collections.push(collection);
        }
    
        let reply = GetCollectionsResponse {
            collections: response_collections,
        };
    
        Ok(Response::new(reply))
    }

    async fn add_row(
        &self,
        request: Request<AddRowRequest>,
    ) -> Result<Response<()>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();
        let mut collections = COLLECTIONS.lock().await;
        
        let schema = SCHEMAS.lock().await;

        if !collections.contains_key(&req.collection_name) || !schema.contains_key(&req.collection_name) {
            return Err(Status::not_found("Collection not found"));
        }

        if !validate_schema(schema.get(&req.collection_name).unwrap(), &req.row) {
            return Err(Status::invalid_argument("Invalid row schema"));
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

        let mut collections = COLLECTIONS.lock().await;

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
        
        let mut collections = COLLECTIONS.lock().await;
        let mut schemas = SCHEMAS.lock().await;
        if collections.contains_key(&req.collection_name) || schemas.contains_key(&req.collection_name) {
            return Err(Status::already_exists("Collection already exists"));
        }
        
        collections.insert(req.collection_name.clone(), vec![]);
        schemas.insert(req.collection_name, req.schema.iter().map(|i| dataflow::DataType::try_from(*i).unwrap()).collect());

        Ok(Response::new(reply))
    }

    async fn delete_collection(
        &self,
        request: Request<DeleteCollectionRequest>,
    ) -> Result<Response<()>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();
        
        let mut collections = COLLECTIONS.lock().await;
        let mut schemas = SCHEMAS.lock().await;
        if !collections.contains_key(&req.collection_name) || !schemas.contains_key(&req.collection_name) {
            return Err(Status::not_found("Collection not found"));
        }
        collections.remove(req.collection_name.as_str());
        schemas.remove(req.collection_name.as_str());

        let reply: () = ();

        Ok(Response::new(reply))
    }

    async fn run_dataflow(
        &self,
        request: Request<RunDataflowRequest>,
    ) -> Result<Response<Self::RunDataflowStream>, Status> {
        println!("Got a request: {:?}", request);
        let req = request.into_inner();
        
        if let Ok(vec) = run_dataflow_so(req.so_path, req.fn_name).await {
            if req.output_csv_path.len() > 0 {
                let mut wtr = csv::WriterBuilder::new()
                    .delimiter(b',')
                    .from_path(req.output_csv_path).map_err(|e| {
                        eprintln!("Failed to create CSV writer: {:?}", e);
                        Status::internal("Failed to create CSV writer")
                    })?;
                for row in vec.iter() {
                    wtr.write_record(row).map_err(|e| {
                        eprintln!("Failed to write record to CSV: {:?}", e);
                        Status::internal("Failed to write record to CSV")
                    })?;
                }
                wtr.flush().map_err(|e| {
                    eprintln!("Failed to flush CSV writer: {:?}", e);
                    Status::internal("Failed to flush CSV writer")
                })?;
                return Ok(Response::new(tokio_stream::iter(vec![])));
            }
            else {
                let responses: Vec<Result<RunDataflowResponse, Status>> = vec.iter().cloned().map(|row| {
                    Ok(RunDataflowResponse { row: row })
                }).collect();
        

                let stream = iter(responses);
                let response_stream = tonic::Response::new(stream);
                return Ok(response_stream);
            }
        }
        else {
            return Err(Status::internal("Failed to run dataflow"));
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let bind_ip = env::var("BIND_IP").unwrap_or_else(|_| "127.0.0.1".to_string());
    let bind_port = env::var("BIND_PORT").unwrap_or_else(|_| "50051".to_string());
    let addr_string = format!("{}:{}", bind_ip, bind_port);
    let addr = addr_string.parse()?;
    let dataflow = MyDataflowService::default();

    Server::builder()
        .add_service(DataflowServiceServer::new(dataflow))
        .serve(addr)
        .await?;

    Ok(())
}

async fn run_dataflow_so(so_path: String, fn_name: String) -> Result<Vec<Vec<String>>, Status> {
    unsafe {
        let lib = Library::new(&so_path).map_err(|e| {
            eprintln!("Failed to load library from path {}: {:?}", so_path, e);
            Status::not_found("Failed to load shared library")
        })?;
        let function: Symbol<unsafe extern "C" fn(&HashMap<String, Vec<Vec<String>>>) -> Vec<Vec<String>>> = match lib.get(fn_name.as_bytes()) {
            Ok(func) => func,
            Err(e) => {
                eprintln!("Failed to get function {}: {:?}", fn_name, e);
                std::mem::drop(lib); // Drop the library before returning
                return Err(Status::not_found("Failed to get function from library"));
            }
        };

        // Acquire the lock on collections
        let collections_guard = COLLECTIONS.lock().await;

        let output: Vec<Vec<String>> = function(&*collections_guard);
        // Drop the library immediately after using it
        std::mem::drop(lib);
        return Ok(output)
    }
}