use std::sync::Arc;
use fancy_regex::Regex;

extern crate rust_span;
use rust_span::{from_span, Span};


fn rgx(pattern: &str, text: &str, span: &Span) -> impl Iterator<Item = Vec<Span>> {
    let re = Regex::new(pattern).unwrap();
    let mut outer_vec = Vec::new();
    let mut start = 0;
    // Use a loop to manually iterate over matches
    while let Ok(Some(caps)) = re.captures_from_pos(text, start) {
        let mut inner_vec = Vec::new();
        if caps.len() == 1 {
            if let Some(m) = caps.get(0) {
                inner_vec.push(Span::new(span.get_doc().clone(), m.start(), m.end(), span.get_name()));
                start = m.end(); // Move to the end of the current match
            }
        } else {
            for i in 1..caps.len() {
            if let Some(m) = caps.get(i) {
                inner_vec.push(Span::new(span.get_doc().clone(), m.start(), m.end(), span.get_name()));
            }
            }
            if let Some(m) = caps.get(0) {
            start = m.end(); // Move to the end of the current match
            }
        }
        outer_vec.push(inner_vec);
    }
    outer_vec.into_iter()
}


pub fn rgx_str_span(pattern: &str, text: &str) -> impl Iterator<Item = Vec<Span>> {
    let doc: Arc::<String> = Arc::new(text.to_string());
    let span = Span::new(doc.clone(), 0, text.len(), "".to_string());
    // Add to document registry (Optional remove function and only allow rgx spans to spans)
    rgx(pattern, text, &span)
}

pub fn rgx_span_span(pattern: &str, span: &Span) -> impl Iterator<Item = Vec<Span>> {
    rgx(pattern, &span.get_doc(), span)
}

pub fn span_as_str(span: &Span) -> impl Iterator<Item = String> {
    std::iter::once(span.as_str().to_string())
}

pub fn span_contained(span1: &Span, span2: &Span) -> impl Iterator<Item= bool> {
    if span1.get_name() == span2.get_name() && span1.get_start() >= span2.get_start() && span1.get_end() <= span2.get_end() {
        return std::iter::once(true);
    }
    else{
        return std::iter::once(false);
    }
}

pub fn deconstruct_span(span: &Span) -> impl Iterator<Item= (String, i32, i32)>{
    return std::iter::once((span.get_name(), span.get_start() as i32, span.get_end() as i32));
}

pub fn rgx_is_match_str(delim: &str, text: &str)-> impl Iterator<Item= bool>{
    return std::iter::once(Regex::new(delim).unwrap().is_match(text).unwrap_or(false));
}

pub fn rgx_is_match_span(delim: &str, span: &Span)-> impl Iterator<Item= bool>{
    return rgx_is_match_str(delim, span.as_str());
}

fn rgx_split(delim: &str, text: &str, intial_tag: &str, base_span: &Span)-> impl Iterator<Item= (Span, Span)>{
    let init_span: Span;
    if intial_tag.is_empty(){
        init_span = Span::new(Arc::<String>::new("Start Tag".to_string()), 0, "Start Tag".len(), "".to_string());
    } else {
        init_span = Span::new(Arc::<String>::new(intial_tag.to_string()), 0, intial_tag.len(), "".to_string());
    }

    let mut matches = rgx_str_span(delim, text);
    let mut results = Vec::new();
    
    let first_span = match matches.next() {
        Some(vec) => vec[0].clone(),
        None => return results.into_iter(),
    };
    if first_span.get_start() != 0 {
        results.push((init_span, from_span(&base_span, 0, first_span.get_start())));
    }

    let mut prev_span = first_span;
    for curr_match in matches.map(|vec| vec[0].clone()) {
        results.push((prev_span.clone(), from_span(&base_span, prev_span.get_end(), curr_match.get_start())));
        prev_span = curr_match;
    }
    results.push((prev_span.clone(), from_span(&base_span, prev_span.get_end(), base_span.get_end())));
    results.into_iter()
}

pub fn rgx_split_str(delim: &str, text: &str, intial_tag: &str)-> impl Iterator<Item= (Span, Span)>{
    let doc = Arc::new(text.to_string());
    let base_span = Span::new(doc.clone(), 0, text.len(), "".to_string());
    // Add to document registry (Optional remove function and only allow spliting spans)

    rgx_split(delim, text, intial_tag, &base_span)
}

pub fn rgx_split_span(delim: &str, span: &Span, intial_tag: &str)-> impl Iterator<Item= (Span, Span)>{
    rgx_split(delim, &span.get_doc(), intial_tag, span)
}

pub fn read_span(text_path: &str) -> impl Iterator<Item = Span> {
    std::iter::once(Span::from_path(text_path))
}

#[cfg(test)]
mod tests {
    use super::*;
    extern crate rust_span;
    use rust_span::Span;
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




}