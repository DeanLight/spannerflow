/// This module provides various functions for working with spans and regular expressions.
/// It includes functions for matching, splitting, and deconstructing spans, as well as
/// reading spans from files.
///
/// # Functions
///
/// - `rgx`: Matches a regex pattern against a text and returns an iterator over vectors of spans.
/// - `rgx_str_span`: Matches a regex pattern against a text and returns an iterator over vectors of spans.
/// - `rgx_span_span`: Matches a regex pattern against a span and returns an iterator over vectors of spans.
/// - `span_as_str`: Converts a span to a string and returns an iterator over the string.
/// - `span_contained`: Checks if one span is contained within another and returns an iterator over a boolean.
/// - `deconstruct_span`: Deconstructs a span into its name, start, and end positions and returns an iterator over a tuple.
/// - `rgx_is_match_str`: Checks if a regex pattern matches a text and returns an iterator over a boolean.
/// - `rgx_is_match_span`: Checks if a regex pattern matches a span and returns an iterator over a boolean.
/// - `rgx_split`: Splits a text based on a regex delimiter and returns an iterator over tuples of spans.
/// - `rgx_split_str`: Splits a text based on a regex delimiter and returns an iterator over tuples of spans.
/// - `rgx_split_span`: Splits a span based on a regex delimiter and returns an iterator over tuples of spans.
/// - `read_span`: Reads a span from a file and returns an iterator over the span.
///
/// # Examples
///
/// ```
/// use std::sync::Arc;
/// use crate::span::{Span, from_span};
///
/// let s = "aaaaa@bbbbbbaa@bb";
/// let span = Span::new(Arc::new(s.to_string()), 0, s.len(), "".to_string());
///
/// assert_eq!(rgx_str_span("(?P<c>(?P<a>a*)@(?P<b>b*))", s).collect::<Vec<_>>(),
/// vec![
///     vec![from_span(&span, 0, 12), from_span(&span, 0, 5), from_span(&span, 6, 12)],
///     vec![from_span(&span, 12, 17), from_span(&span, 12, 14), from_span(&span, 15, 17)]
/// ]);
/// ```
use std::sync::Arc;
use pcre2::bytes::Regex;
use crate::span::{Span, from_span};


/// Matches a regex pattern against a text and returns an iterator over vectors of spans.
/// 
/// # Arguments
/// 
/// * `pattern` - A string slice that holds the regex pattern.
/// * `text` - A string slice that holds the text to be matched against the pattern.
/// * `span` - A reference to a `Span` object that represents the span of the text.
/// 
/// # Returns
/// 
/// An iterator over vectors of spans. Each vector represents a match and its capturing groups.
/// 
/// # Examples
/// 
/// ```
/// use std::sync::Arc;
/// use crate::span::{Span, from_span};
/// 
/// let s = "aaaaa@bbbbbbaa@bb";
/// let span = Span::new(Arc::new(s.to_string()), 0, s.len(), "".to_string());
/// 
/// let matches: Vec<Vec<Span>> = rgx("(?P<c>(?P<a>a*)@(?P<b>b*))", s, &span).collect();
/// assert_eq!(matches, vec![
///     vec![from_span(&span, 0, 12), from_span(&span, 0, 5), from_span(&span, 6, 12)],
///     vec![from_span(&span, 12, 17), from_span(&span, 12, 14), from_span(&span, 15, 17)]
/// ]);
/// ```
fn rgx(pattern: &str, text: &str, span: &Span) -> impl Iterator<Item = Vec<Span>> {
    let re = Regex::new(pattern).unwrap();
    let text_bytes = text.as_bytes();
    re.captures_iter(text_bytes)
    .filter_map(|cap_result| cap_result.ok())
    .map(|captures| {
        if captures.len() == 1 {
            vec![captures.get(0).map(|m| from_span(span, m.start(), m.end())).unwrap()]
        } else {
            (1..captures.len()).map(|i| {
                captures.get(i).map(|m| from_span(span, m.start(), m.end())).unwrap()
            }).collect()
        }
    }).collect::<Vec<_>>().into_iter()
}


pub fn rgx_str_span(pattern: &str, text: &str) -> impl Iterator<Item = Vec<Span>> {
    let doc: Arc::<String> = Arc::new(text.to_string());
    let span = Span::new(doc.clone(), 0, text.len(), "".to_string());
    // Add to document registry (Optional remove function and only allow rgx spans to spans)
    rgx(pattern, text, &span)
}

pub fn rgx_span_span(pattern: &str, span: &Span) -> impl Iterator<Item = Vec<Span>> {
    rgx(pattern, span.as_str(), span)
}

pub fn span_as_str(span: &Span) -> impl Iterator<Item = String> {
    std::iter::once(span.as_str().to_string())
}

pub fn span_contained(span1: &Span, span2: &Span) -> impl Iterator<Item= bool> {
    if span1.get_name() == span2.get_name() && span1.get_start() >= span2.get_start() && span1.get_end() <= span2.get_end() {
        std::iter::once(true)
    }
    else{
        std::iter::once(false)
    }
}

pub fn deconstruct_span(span: &Span) -> impl Iterator<Item= (String, i32, i32)>{
    std::iter::once((span.get_name(), span.get_start() as i32, span.get_end() as i32))
}

pub fn rgx_is_match_str(delim: &str, text: &str)-> impl Iterator<Item= bool>{
    let text_bytes = text.as_bytes();
    std::iter::once(Regex::new(delim).unwrap().is_match(text_bytes).unwrap_or(false))
}

pub fn rgx_is_match_span(delim: &str, span: &Span)-> impl Iterator<Item= bool>{
    return rgx_is_match_str(delim, span.as_str());
}

fn rgx_split(delim: &str, text: &str, intial_tag: &str, base_span: &Span)-> impl Iterator<Item= (Span, Span)>{
    let init_span: Span = if intial_tag.is_empty(){
        Span::new(Arc::<String>::new("Start Tag".to_string()), 0, "Start Tag".len(), "".to_string())
    } else {
        Span::new(Arc::<String>::new(intial_tag.to_string()), 0, intial_tag.len(), "".to_string())
    };

    let mut matches = rgx_str_span(delim, text);
    let mut results = Vec::new();
    
    let first_span = match matches.next() {
        Some(vec) => vec[0].clone(),
        None => return results.into_iter(),
    };
    if first_span.get_start() != 0 {
        results.push((init_span, from_span(base_span, 0, first_span.get_start())));
    }

    let mut prev_span = first_span;
    for curr_match in matches.map(|vec| vec[0].clone()) {
        results.push((prev_span.clone(), from_span(base_span, prev_span.get_end(), curr_match.get_start())));
        prev_span = curr_match;
    }
    results.push((prev_span.clone(), from_span(base_span, prev_span.get_end(), base_span.get_end())));
    results.into_iter()
}

pub fn rgx_split_str(delim: &str, text: &str, intial_tag: &str)-> impl Iterator<Item= (Span, Span)>{
    let doc = Arc::new(text.to_string());
    let base_span = Span::new(doc.clone(), 0, text.len(), "".to_string());
    // Add to document registry (Optional remove function and only allow spliting spans)

    rgx_split(delim, text, intial_tag, &base_span)
}

pub fn rgx_split_span(delim: &str, span: &Span, intial_tag: &str)-> impl Iterator<Item= (Span, Span)>{
    rgx_split(delim, span.as_str(), intial_tag, span)
}

pub fn read_span(text_path: &str) -> impl Iterator<Item = Span> {
    std::iter::once(Span::from_path(text_path))
}


#[cfg(test)]
mod tests{
    use super::*;
    use std::fs::File;
    use std::io::Write;
    use std::fs;

    #[test]
    fn test_rgx_str_span(){
        let s = "aaaaa@bbbbbbaa@bb";
        let sa = Arc::new(s.to_string());
        let span = Span::new(sa, 0, s.len(), "".to_string());
        
        assert_eq!(rgx_str_span("(?P<c>(?P<a>a*)@(?P<b>b*))", s).collect::<Vec<_>>(), 
        vec![
            vec![from_span(&span, 0, 12), from_span(&span, 0, 5), from_span(&span, 6, 12)],
            vec![from_span(&span, 12, 17), from_span(&span, 12, 14), from_span(&span, 15, 17)]
        ]);
        
        assert_eq!(rgx_str_span("((?:a*)@(?:b*))", s).collect::<Vec<_>>(), 
        vec![
            vec![from_span(&span, 0, 12)],
            vec![from_span(&span, 12, 17)]
        ]);
    }
    
    #[test]
    fn test_rgx_span_span(){
        let s = "aaaaa@bbbbbbaa@bb";
        let span = Span::new(Arc::new(s.to_string()), 0, s.len(), "".to_string());
        
        assert_eq!(rgx_span_span("(?P<c>(?P<a>a*)@(?P<b>b*))", &span).collect::<Vec<_>>(), 
        vec![
            vec![from_span(&span, 0, 12), from_span(&span, 0, 5), from_span(&span, 6, 12)],
            vec![from_span(&span, 12, 17), from_span(&span, 12, 14), from_span(&span, 15, 17)]
        ]);
        
        assert_eq!(rgx_span_span("((?:a*)@(?:b*))", &span).collect::<Vec<_>>(), 
        vec![
            vec![from_span(&span, 0, 12)],
            vec![from_span(&span, 12, 17)]
        ]);
    }
    #[test]
    fn test_span_contained(){
        let s1: &str = "hello darkness my old friend";
        let s2: &str = "I come to talk to you again";
        let doc1 : Span = Span::new(Arc::<String>::new(s1.to_string()), 0, s1.len(), "doc1".to_string());
        let doc2 : Span = Span::new(Arc::<String>::new(s2.to_string()), 0, s2.len(), "doc2".to_string());
        let span1: Span = from_span(&doc1, 1, 10);
        let span2: Span = from_span(&doc1, 0, 11);
        let span3: Span = from_span(&doc1, 2, 12);
        let span4: Span = from_span(&doc2, 3, 5);
        
        assert_eq!(span_contained(&span1, &span2).collect::<Vec<_>>(), vec![true]);
        assert_eq!(span_contained(&span2, &span1).collect::<Vec<_>>(), vec![false]);
        assert_eq!(span_contained(&span1, &span3).collect::<Vec<_>>(), vec![false]);
        assert_eq!(span_contained(&span1, &span4).collect::<Vec<_>>(), vec![false]);
    }

    #[test]
    fn test_deconstruct_span(){
        let s1: &str = "hello darkness my old friend";
        let s2: &str = "I come to talk to you again";
        let doc1 : Span = Span::new(Arc::<String>::new(s1.to_string()), 0, s1.len(), "doc1".to_string());
        let doc2 : Span = Span::new(Arc::<String>::new(s2.to_string()), 0, s2.len(), "doc2".to_string());
        let span1: Span = from_span(&doc1, 1, 10);
        let span2: Span = from_span(&doc1, 0, 11);
        let span3: Span = from_span(&doc1, 2, 12);
        let span4: Span = from_span(&doc2, 3, 5);

        assert_eq!(deconstruct_span(&span1).collect::<Vec<_>>(), vec![("doc1".to_string(), 1, 10)]);
        assert_eq!(deconstruct_span(&span2).collect::<Vec<_>>(), vec![("doc1".to_string(), 0, 11)]);
        assert_eq!(deconstruct_span(&span3).collect::<Vec<_>>(), vec![("doc1".to_string(), 2, 12)]);
        assert_eq!(deconstruct_span(&span4).collect::<Vec<_>>(), vec![("doc2".to_string(), 3, 5)]);
    }

    #[test]
    fn test_rgx_is_match_str(){
        assert_eq!(rgx_is_match_str("(a*)@(b*)", "dddaaaaa@bbbbbbaa@bb").collect::<Vec<_>>(), vec![true]);
        assert_eq!(rgx_is_match_str("(a*)@(e+)", "dddaaaaa@bbbbbbaa@bb").collect::<Vec<_>>(), vec![false]);
    }

    #[test]
    fn test_rgx_is_match_span(){
        let document = "dddaaaaa@bbbbbbaa@bb";
        let span_document= Span::new(Arc::<String>::new(document.to_string()), 0, document.len(), "doc1".to_string());
        assert_eq!(rgx_is_match_span("(a*)@(b*)", &span_document).collect::<Vec<_>>(), vec![true]);
        assert_eq!(rgx_is_match_span("(a*)@(e+)", &span_document).collect::<Vec<_>>(), vec![false]);
    }
    
    #[test]
    fn test_rgx_split_str() {
        let result_1 = rgx_split_str("a|x", "bbbannnnxdddaca", "Start Tag").map(|(s1, s2)| {
            (s1.as_str().to_string(), s2.as_str().to_string())
        }).collect::<Vec<_>>();
        assert_eq!(result_1, vec![("Start Tag".to_string(), "bbb".to_string()),
            ("a".to_string(), "nnnn".to_string()),
            ("x".to_string(), "ddd".to_string()),
            ("a".to_string(), "c".to_string()),
            ("a".to_string(), "".to_string())]);
            
        let result_2 = rgx_split_str("a|x", "abbbannnnxdddaca", "Start Tag").map(|(s1, s2)| {
            (s1.as_str().to_string(), s2.as_str().to_string())
        }).collect::<Vec<_>>();
        assert_eq!(result_2, vec![("a".to_string(), "bbb".to_string()),
            ("a".to_string(), "nnnn".to_string()),
            ("x".to_string(), "ddd".to_string()),
            ("a".to_string(), "c".to_string()),
            ("a".to_string(), "".to_string())]);
    }

    #[test]
    fn test_rgx_split_span() {
        let span1 = Span::new(Arc::new("bbbannnnxdddaca".to_string()), 0, 15, "".to_string());
        let result_1 = rgx_split_span("a|x", &span1, "Start Tag").map(|(s1, s2)| {
            (s1.as_str().to_string(), s2.as_str().to_string())
        }).collect::<Vec<_>>();
        assert_eq!(result_1, vec![("Start Tag".to_string(), "bbb".to_string()),
            ("a".to_string(), "nnnn".to_string()),
            ("x".to_string(), "ddd".to_string()),
            ("a".to_string(), "c".to_string()),
            ("a".to_string(), "".to_string())]);
            
        let span2 =  Span::new(Arc::new("abbbannnnxdddaca".to_string()), 0, 16, "".to_string());
        let result_2 = rgx_split_span("a|x", &span2, "Start Tag").map(|(s1, s2)| {
            (s1.as_str().to_string(), s2.as_str().to_string())
        }).collect::<Vec<_>>();
        assert_eq!(result_2, vec![("a".to_string(), "bbb".to_string()),
            ("a".to_string(), "nnnn".to_string()),
            ("x".to_string(), "ddd".to_string()),
            ("a".to_string(), "c".to_string()),
            ("a".to_string(), "".to_string())]);
    }

    #[test]
    fn test_read_span_with_file_creation() {
        let test_file_path = "test.txt";
        let test_content = "This is a test file content.";

        // Create the file
        let mut file = File::create(test_file_path).expect("Unable to create test file");
        file.write_all(test_content.as_bytes()).expect("Unable to write to test file");

        // Run the test
        let span = read_span(test_file_path);
        for s in span {
            let result = rgx_span_span(r"(\w+)", &s);
            assert_eq!(result.collect::<Vec<_>>(), vec![
                vec![from_span(&s, 0, 4)],
                vec![from_span(&s, 5, 7)],
                vec![from_span(&s, 8, 9)],
                vec![from_span(&s, 10, 14)],
                vec![from_span(&s, 15, 19)],
                vec![from_span(&s, 20, 27)]]);
        }

        // Delete the file
        fs::remove_file(test_file_path).expect("Unable to delete test file");
    }


    #[test]
    fn test_weired_regex(){
        let doc = Arc::new("patient presents to be tested for COVID-19. His family recently tested positive for COVID-19.".to_string());
        let span: Span = Span::new(doc, 0, 93 , "".to_string());
        let subspan1 = from_span(&span, 0, 43);
        let subspan2 = from_span(&span, 44, 93);
        println!("Subspan: {:?}", subspan1);
        println!("Subspan: {:?}", subspan2);

        let patt = r"(?i)(?:(?:(?:test(?:\S+)?)?positive(?: for)?|notif(?:y|ied) of positive (?:results?|test(?:\S+)?|status))(?: (?!)\S+)*? COVID-19)";
        let result1 = rgx_span_span(patt, &subspan1).collect::<Vec<_>>();
        assert_eq!(result1.len(), 0);
 
        let result2 = rgx_span_span(patt, &subspan2).collect::<Vec<_>>();
        println!("{:?}", result2[0][0]);
        assert_eq!(result2.len(), 1);
        assert_eq!(result2[0][0], from_span(&span, 71, 92))
    }
}
