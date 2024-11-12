use sha1::{Sha1, Digest};
use std::cmp::Ordering;
use std::hash::{Hash, Hasher};
use std::sync;
use std::str::FromStr;
use hex;
use regex::Regex;
use std::sync::Arc;

extern "C" {
    fn add_document(id: String, doc: sync::Arc<String>);
    fn get_document(id: String) -> Option<sync::Arc<String>>;
}

fn small_hash(txt: &str, length: usize) -> String {
    let mut hasher = Sha1::new();
    hasher.update(txt.as_bytes());
    let results = hasher.finalize();
    hex::encode(results)[..length].to_string()
}

#[derive(Debug)]
pub enum SpanParseError {
    InvalidFormat,
    ParseIntError,
}

/// A struct that represents a span of text in a document.
#[derive(Clone, Serialize, Deserialize, Hash)]
pub struct Span {
    doc: Arc<str>,
    start: usize,
    end: usize,
    name: String,
}

impl Span {
    /// 
    pub fn new(doc: &str, start: usize, end: usize, name: String) -> Span {
        let mut span_name = name;
        if span_name.is_empty() {
            span_name = small_hash(&doc[start..end], 6);
        }
        Span {
            doc: Arc::from(doc),
            start,
            end,
            name: span_name,
        }
    }

    fn from_path(path: &str, start: usize, end: usize) -> Span {
        let doc_string = std::fs::read_to_string(path).unwrap();
        Span::new(&doc_string, start, end, "".to_string())
    }

    fn slice(&self, start: usize, end: usize) -> Span {
        if start > end {
            panic!(
                "Start index greater than end index, got start: {}, end: {}",
                start, end
            );
        }
        if end > self.doc.len() {
            panic!(
                "End index greater than length of span, got end: {}, length: {}",
                end, self.doc.len()
            );
        }

        Span {
            doc: self.doc.clone(),
            start: self.start + start,
            end: self.start + end,
            name: self.name.clone(),
        }
        
    }

    fn len(&self) -> usize {
        self.end - self.start
    }
    
    pub fn get_doc(&self) -> Arc<str> {
        self.doc.clone()
    }

    pub fn get_start(&self) -> usize {
        self.start
    }

    pub fn get_end(&self) -> usize {
        self.end
    }

    pub fn get_name(&self) -> String {
        self.name.clone()
    }

    pub fn as_str(&self) -> &str {
        &self.doc[self.start..self.end]
    }
}

impl FromStr for Span {
    type Err = SpanParseError;

    fn from_str(s: &str) -> Result<Self, Self::Err>  {
        let re = Regex::new(r#"\[@(\w+),(\d+),(\d+)\) "(.+)""#).unwrap();
        if let Some(caps) = re.captures(s) {
            let name = caps.get(1).unwrap().as_str().to_string();
            let start = caps.get(2).unwrap().as_str().parse::<usize>().unwrap();
            let end = caps.get(3).unwrap().as_str().parse::<usize>().unwrap();
            let text = caps.get(4).unwrap().as_str().to_string();
            println!("name: {}, start: {}, end: {} text: {}", name.clone(), start, end, text);
            // TODO: Add document registry
            // unsafe {let document = get_document(name.clone());}
            // match document {
            //     Some(doc) => {
            //         Span::new(&doc, start, end, name)
            //     },
            //     None => {
            //         let doc = Arc::new(text.clone());
            //         unsafe {add_document(name.clone(), text.clone().into());}
            //         Span::new(&doc, start, end, name)
            //     }
            // }
            Ok(Span::new(&text, start, end, name))
        }
        else {
            eprintln!("Invalid format for span: {}", s);
            Err(SpanParseError::InvalidFormat)
        }
        // regex extraction of span paramters.
        // check if documentid exists in documet registry
        // if not add document to registry
        // return span with arc<string> to the document      
    }
}

impl std::fmt::Debug for Span{
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "[@{},{},{}) \"{}\"", self.name, self.start, self.end, &self.doc[self.start..self.end])
    }
}

impl std::fmt::Display for Span {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "[@{},{},{}) \"{}\"", self.name, self.start, self.end, &self.doc[self.start..self.end])
    }
}

impl<'a> PartialEq for Span {
    fn eq(&self, other: &Self) -> bool {
        self.start == other.start && self.end == other.end && self.name == other.name
    }
}

impl<'a> Eq for Span {}

impl PartialOrd for Span {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

/// Ord implementation for Span, needed for dataflow to work
impl Ord for Span {
    fn cmp(&self, other: &Self) -> Ordering {
        self.doc.cmp(&other.doc)
            .then_with(|| self.start.cmp(&other.start))
            .then_with(|| self.end.cmp(&other.end))
    }
}

/// Create a new span from an existing span
pub fn from_span(span: &Span, start: usize, end: usize) -> Span {
    span.slice(start, end)
}
