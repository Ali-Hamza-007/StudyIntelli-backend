import pymupdf as fitz

class PDFExtractionService:
    @staticmethod
    def extract_text(file_stream) -> str:
        text = ""
        try:
            # The file has just been saved, so the stream pointer is at the end.
            # It's safer and more efficient to open the file directly from its path on disk.
            doc = fitz.open(file_stream.path)
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            raise ValueError(f"Could not extract text from PDF: {str(e)}")
