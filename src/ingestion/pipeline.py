"""
Document ingestion pipeline.
Orchestrates: file upload → PDF processing → chunking → embedding → storage.
"""

import os
import shutil
import logging
from pathlib import Path

from src.config import settings, ensure_directories
from src.models.schemas import DocumentInfo, Chunk
from src.ingestion.pdf_processor import PDFProcessor
from src.ingestion.table_extractor import TableExtractor
from src.ingestion.image_extractor import ImageExtractor
from src.ingestion.ocr_processor import OCRProcessor
from src.ingestion.vision_analyzer import VisionAnalyzer
from src.ingestion.equation_extractor import EquationExtractor
from src.ingestion.chunker import SemanticChunker
from src.storage.embedding_service import EmbeddingService
from src.storage.vector_store import VectorStore
from src.storage.document_store import DocumentStore

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    End-to-end document ingestion pipeline.
    Handles PDF upload, text extraction, chunking, embedding, and storage.
    """

    def __init__(self):
        ensure_directories()
        self.pdf_processor = PDFProcessor()
        self.table_extractor = TableExtractor()
        self.image_extractor = ImageExtractor()
        self.ocr_processor = OCRProcessor()
        self.vision_analyzer = VisionAnalyzer()
        self.equation_extractor = EquationExtractor()
        self.chunker = SemanticChunker()
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()
        self.document_store = DocumentStore()

    def ingest_file(self, file_path: str, original_filename: str) -> DocumentInfo:
        """
        Ingest a document file into the system.

        Args:
            file_path: Path to the uploaded file (temporary location).
            original_filename: Original name of the uploaded file.

        Returns:
            DocumentInfo with processing status.
        """
        logger.info(f"Starting ingestion for: {original_filename}")

        # Step 1: Create document record
        doc = DocumentInfo(
            filename=original_filename,
            file_path="",
            file_type=Path(original_filename).suffix.lstrip(".").lower(),
        )

        # Step 2: Save file to upload directory
        dest_path = os.path.join(settings.upload_dir, f"{doc.id}_{original_filename}")
        shutil.copy2(file_path, dest_path)
        doc.file_path = dest_path

        # Step 3: Record in document store
        doc.status = "processing"
        self.document_store.add_document(doc)

        try:
            # Step 4: Multimodal extraction
            logger.info("Extracting structured content (text, tables, images)...")
            text_elements = self.pdf_processor.extract(dest_path)
            table_elements = self.table_extractor.extract(dest_path)
            image_elements = self.image_extractor.extract(dest_path, doc_id=doc.id)
            
            doc.total_pages = self.pdf_processor.get_page_count(dest_path)
            
            # Step 5: Process extracted images (Vision Analysis + OCR)
            processed_elements = []
            processed_elements.extend(text_elements)
            processed_elements.extend(table_elements)
            
            for img_elem in image_elements:
                # For each image, perform Vision analysis and OCR
                # We categorize based on Gemini's initial classification
                logger.info(f"Analyzing image found on page {img_elem.page_number}...")
                
                # Vision analysis provides a technical description
                vision_description = self.vision_analyzer.analyze(img_elem.image_path)
                
                # Heuristically check if this is likely an equation
                is_equation = "equation" in vision_description.lower() or "formula" in vision_description.lower()
                
                if is_equation:
                    eq_data = self.equation_extractor.extract_from_image(img_elem.image_path)
                    img_elem.element_type = "equation"
                    img_elem.content = eq_data['latex']
                    img_elem.table_data = {"explanation": eq_data['explanation']} # temp storage
                else:
                    # Otherwise treat as figure and use vision description
                    img_elem.content = vision_description
                
                processed_elements.append(img_elem)

            if not processed_elements:
                logger.warning(f"No content extracted from {original_filename}")
                doc.status = "failed"
                self.document_store.update_status(doc.id, "failed")
                return doc

            # Step 6: Chunk the content
            logger.info(f"Chunking {len(processed_elements)} multimodal elements...")
            chunks = self.chunker.chunk(processed_elements, original_filename)

            if not chunks:
                logger.warning(f"No chunks created for {original_filename}")
                doc.status = "failed"
                self.document_store.update_status(doc.id, "failed")
                return doc

            # Step 6: Generate embeddings
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            texts = [chunk.content for chunk in chunks]
            embeddings = self.embedding_service.embed_texts(texts)

            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding

            # Step 7: Store in vector database
            logger.info("Storing chunks in vector database...")
            num_stored = self.vector_store.add_chunks(chunks)
            doc.total_chunks = num_stored

            # Step 8: Update document status
            doc.status = "completed"
            self.document_store.update_status(doc.id, "completed", num_stored, doc.total_pages)

            logger.info(
                f"Ingestion complete: {original_filename} "
                f"({doc.total_pages} pages, {num_stored} chunks)"
            )
            return doc

        except Exception as e:
            logger.error(f"Ingestion failed for {original_filename}: {e}")
            doc.status = "failed"
            self.document_store.update_status(doc.id, "failed")
            raise

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document and all its chunks."""
        doc = self.document_store.get_document(doc_id)
        if not doc:
            return False

        # Delete chunks from vector store
        self.vector_store.delete_by_source(doc.filename)

        # Delete file from disk
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)

        # Delete from document store
        self.document_store.delete_document(doc_id)
        logger.info(f"Deleted document: {doc.filename} ({doc_id})")
        return True

    def get_all_documents(self) -> list[DocumentInfo]:
        """Get all ingested documents."""
        return self.document_store.get_all_documents()
