use sha1::{Sha1, Digest};
use std::cmp::Ordering;
use std::hash::{Hash, Hasher};
use std::sync;
use std::str::FromStr;
use hex;
use regex::Regex;
use std::sync::Arc;
use std::path::Path;
use rust_span::{add_document, get_document};


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
    doc: Arc<String>,
    start: usize,
    end: usize,
    name: String,
}

impl Span {
    /// 
    pub fn new(doc: Arc<String>, start: usize, end: usize, name: String) -> Span {
        let mut span_name = name;
        if span_name.is_empty() {
            span_name = small_hash(&doc[start..end], 6);
        }
        Span {
            doc,
            start,
            end,
            name: span_name,
        }
    }

    pub fn from_path(path: &str) -> Span {
        let doc_string = std::fs::read_to_string(path).unwrap();
        let file_name = std::path::Path::new(path)
            .file_name()
            .unwrap()
            .to_str()
            .unwrap()
            .to_string();
        let end = doc_string.len();
        let doc = Arc::new(doc_string);
        Span::new(doc, 0, end, file_name)
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

    pub fn len(&self) -> usize {
        self.end - self.start
    }
    
    pub fn get_doc(&self) -> Arc<String> {
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
            unsafe {
                let document = get_document(name.clone());
                match document {
                    Some(doc) => {
                        return Ok(Span::new(doc, start, end, name));
                    },
                    None => {
                        let doc = Arc::new(text.clone());
                        add_document(name.clone(), text.clone().into());
                        return Ok(Span::new(doc, start, end, name));
                    }
                }
            }
            let doc = Arc::new(text.clone());
            Ok(Span::new(doc.clone(), start, end, name))
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

mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;

    #[test]
    fn test_span_new() {
        let doc = Arc::new("Hello, world!".to_string());
        let span = Span::new(doc.clone(), 0, 5, "greeting".to_string());
        assert_eq!(span.get_doc(), doc);
        assert_eq!(span.get_start(), 0);
        assert_eq!(span.get_end(), 5);
        assert_eq!(span.get_name(), "greeting");
        assert_eq!(span.as_str(), "Hello");
    }

    #[test]
    fn test_span_slice() {
        let doc = Arc::new("Hello, world!".to_string());
        let span = Span::new(doc.clone(), 0, 12, "greeting".to_string());
        let sliced_span = span.slice(7, 12);
        assert_eq!(sliced_span.get_doc(), doc);
        assert_eq!(sliced_span.get_start(), 7);
        assert_eq!(sliced_span.get_end(), 12);
        assert_eq!(sliced_span.get_name(), "greeting");
        assert_eq!(sliced_span.as_str(), "world");
    }

    #[test]
    #[should_panic(expected = "Start index greater than end index")]
    fn test_span_slice_invalid_indices() {
        let doc = Arc::new("Hello, world!".to_string());
        let span = Span::new(doc.clone(), 0, 12, "greeting".to_string());
        span.slice(12, 7);
    }

    #[test]
    fn test_span_len() {
        let doc = Arc::new("Hello, world!".to_string());
        let span = Span::new(doc.clone(), 0, 5, "greeting".to_string());
        assert_eq!(span.len(), 5);
    }

    #[test]
    fn test_span_from_str() {
        let span_str = r#"[@greeting,0,5) "Hello""#;
        let span = Span::from_str(span_str).unwrap();
        assert_eq!(span.get_name(), "greeting");
        assert_eq!(span.get_start(), 0);
        assert_eq!(span.get_end(), 5);
        assert_eq!(span.as_str(), "Hello");
    }

    #[test]
    fn test_span_display() {
        let doc = Arc::new("Hello, world!".to_string());
        let span = Span::new(doc.clone(), 0, 5, "greeting".to_string());
        assert_eq!(format!("{}", span), r#"[@greeting,0,5) "Hello""#);
    }

    #[test]
    fn test_span_debug() {
        let doc = Arc::new("Hello, world!".to_string());
        let span = Span::new(doc.clone(), 0, 5, "greeting".to_string());
        assert_eq!(format!("{:?}", span), r#"[@greeting,0,5) "Hello""#);
    }

    #[test]
    fn test_span_partial_eq() {
        let doc = Arc::new("Hello, world!".to_string());
        let span1 = Span::new(doc.clone(), 0, 5, "greeting".to_string());
        let span2 = Span::new(doc.clone(), 0, 5, "greeting".to_string());
        assert_eq!(span1, span2);
    }

    #[test]
    fn test_span_ord() {
        let doc = Arc::new("Hello, world!".to_string());
        let span1 = Span::new(doc.clone(), 0, 5, "greeting".to_string());
        let span2 = Span::new(doc.clone(), 6, 12, "world".to_string());
        assert!(span1 < span2);
    }

    #[test]
    fn test_from_path() {
        let tmp_file_path = "/tmp/test_document.txt";
        let mut file = File::create(tmp_file_path).unwrap();
        writeln!(file, "Hello, world!").unwrap();

        let span = Span::from_path(tmp_file_path);
        assert_eq!(span.get_name(), "test_document.txt");
        assert_eq!(span.get_start(), 0);
        assert_eq!(span.get_end(), 14);

        let sub_span = span.slice(7, 12);
        assert_eq!(sub_span.get_name(), "test_document.txt");
        assert_eq!(sub_span.get_start(), 7);
        
        
        std::fs::remove_file(tmp_file_path).unwrap();
    }
    
    // Enable this test after implementing document registry
    #[test]
    fn test_span_from_str_with_new_document() {
       let span_str = r#"[@doc1,0,13) "Hello, world!""#;
       let span = Span::from_str(span_str).unwrap();
       assert_eq!(span.get_name(), "doc1");
       assert_eq!(span.get_start(), 0);
       assert_eq!(span.get_end(), 13);
       assert_eq!(span.as_str(), "Hello, world!");

       let sub_span_str = r#"[@doc1,7,12) "world""#;
       let sub_span = Span::from_str(sub_span_str).unwrap();
       assert_eq!(sub_span.get_name(), "doc1");
       assert_eq!(sub_span.get_start(), 7);
       assert_eq!(sub_span.get_end(), 12);
       assert_eq!(sub_span.as_str(), "world");
    }

    
}
