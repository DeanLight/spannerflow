use std::sync;
use std::collections::HashMap;


lazy_static::lazy_static! {
    // change id to string, value need to be Arc<string>
    static ref DOCUMENTS: sync::Mutex<HashMap<String, sync::Arc<String>>> = sync::Mutex::new(HashMap::new());
}

// change id to string, change to dylib - change to get/add: if exists return pointer if not, create one.
#[no_mangle]
pub fn add_document(id: String, doc: sync::Arc<String>) {
    let mut documents = DOCUMENTS.lock().unwrap();
    documents.insert(id, doc);
}
// change to get_span - input id, start, end- return copy of substring of document. expose this to the API
#[no_mangle]
pub fn get_document(id: String) -> Option<sync::Arc<String>> {
    let documents = DOCUMENTS.lock().unwrap();
    match documents.get(&id) {
        Some(doc) => Some(sync::Arc::clone(doc)),
        None => None,
    }
}
