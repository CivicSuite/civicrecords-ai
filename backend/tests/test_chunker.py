from app.ingestion.chunker import chunk_text, chunk_pages, estimate_tokens

def test_estimate_tokens():
    assert estimate_tokens("hello world") > 0
    assert estimate_tokens("a" * 400) == 100

def test_chunk_text_single_chunk():
    text = "Hello world. This is a test."
    chunks = chunk_text(text, chunk_size=500)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].index == 0

def test_chunk_text_multiple_chunks():
    sentences = [f"Sentence number {i} has some content." for i in range(50)]
    text = " ".join(sentences)
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    for i, chunk in enumerate(chunks):
        assert chunk.index == i
    full_reconstructed = " ".join(c.text for c in chunks)
    for s in sentences:
        assert s in full_reconstructed

def test_chunk_text_overlap():
    sentences = [f"Sentence {i} with enough words to count." for i in range(20)]
    text = " ".join(sentences)
    chunks = chunk_text(text, chunk_size=50, chunk_overlap=15)
    if len(chunks) >= 2:
        last_words_chunk0 = chunks[0].text.split()[-3:]
        assert any(w in chunks[1].text for w in last_words_chunk0)

def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []

def test_chunk_pages():
    pages = [
        {"text": "Page one content here.", "page_number": 1},
        {"text": "Page two has different content.", "page_number": 2},
    ]
    chunks = chunk_pages(pages, chunk_size=500)
    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2
    assert chunks[0].index == 0
    assert chunks[1].index == 1

def test_chunk_pages_preserves_page_number():
    long_text = " ".join([f"Sentence {i} on this page." for i in range(30)])
    pages = [{"text": long_text, "page_number": 5}]
    chunks = chunk_pages(pages, chunk_size=50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.page_number == 5
