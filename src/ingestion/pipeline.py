"""
Document ingestion pipeline.
Orchestrates: file upload → PDF processing → chunking → embedding → storage.
"""

import hashlib
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
from src.ingestion.chunker import RecursiveChunker
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
        self.chunker = RecursiveChunker()
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

        # Step 0: Duplicate detection via SHA-256 hash
        file_hash = hashlib.sha256(open(file_path, "rb").read()).hexdigest()
        existing_doc = self.document_store.get_by_hash(file_hash)
        if existing_doc:
            logger.info(
                f"Duplicate file detected: '{original_filename}' matches existing "
                f"document '{existing_doc.filename}' (id={existing_doc.id}). "
                f"Returning existing document."
            )
            return existing_doc

        # Step 1: Create document record
        doc = DocumentInfo(
            filename=original_filename,
            file_path="",
            file_type=Path(original_filename).suffix.lstrip(".").lower(),
            file_hash=file_hash,
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
            self.document_store.update_progress(doc.id, "Extracting text (step 1/6)")
            text_elements = self.pdf_processor.extract(dest_path)
            self.document_store.update_progress(doc.id, "Extracting tables (step 2/6)")
            table_elements = self.table_extractor.extract(dest_path)
            self.document_store.update_progress(doc.id, "Extracting images (step 3/6)")
            image_elements = self.image_extractor.extract(dest_path, doc_id=doc.id)

            doc.total_pages = self.pdf_processor.get_page_count(dest_path)
            
            # Step 5: Process extracted images (Vision Analysis + OCR)
            self.document_store.update_progress(doc.id, "Analyzing images with vision AI (step 3/6)")
            processed_elements = []
            processed_elements.extend(text_elements)
            processed_elements.extend(table_elements)

            # Build a set of pages with low text yield (fewer than 100 words)
            # so we know when to run OCR on extracted images.
            page_word_counts: dict[int, int] = {}
            for elem in text_elements:
                pn = elem.page_number
                page_word_counts[pn] = page_word_counts.get(pn, 0) + len(elem.content.split())

            # Process each image: run vision analysis at ingestion time, then OCR
            # for low-text pages, then equation extraction.
            for img_elem in image_elements:
                page_num = img_elem.page_number
                image_path = img_elem.image_path
                logger.info(
                    f"Adding image from page {page_num} "
                    f"(running vision analysis at ingestion time)"
                )

                # --- OCR for low-text pages -----------------------------------
                ocr_text = ""
                if page_word_counts.get(page_num, 0) < 100 and image_path:
                    try:
                        ocr_elem = self.ocr_processor.extract_from_image(
                            image_path, page_number=page_num
                        )
                        if ocr_elem.content.strip():
                            ocr_text = ocr_elem.content.strip()
                            logger.info(
                                f"OCR produced {len(ocr_text.split())} words "
                                f"for page {page_num} image"
                            )
                    except Exception as e:
                        logger.warning(f"OCR failed for {image_path}: {e}")

                # --- Equation extraction (LaTeX) ------------------------------
                latex_result: dict = {}
                if image_path:
                    try:
                        latex_result = self.equation_extractor.extract_from_image(image_path)
                    except Exception as e:
                        logger.warning(f"Equation extraction failed for {image_path}: {e}")

                # --- Vision analysis (Gemini) at ingestion time ---------------
                vision_description = ""
                if image_path:
                    try:
                        description = self.vision_analyzer.analyze(image_path)
                        # Accept the description only when it is substantive
                        # and not a generic error/placeholder message.
                        if (
                            description
                            and "unavailable" not in description.lower()
                            and "disabled" not in description.lower()
                            and len(description.strip()) > 20
                        ):
                            vision_description = description.strip()
                            logger.info(
                                f"Vision analysis completed for page {page_num} image "
                                f"({len(vision_description)} chars)"
                            )
                        else:
                            logger.info(
                                f"Vision analysis returned placeholder for page {page_num}; "
                                f"keeping default description"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Vision analysis failed for {image_path}: {e}. "
                            f"Keeping placeholder description."
                        )

                # Build content string (vision description or placeholder + OCR)
                if vision_description:
                    base_description = (
                        f"[Figure on page {page_num}] {vision_description}"
                    )
                else:
                    base_description = (
                        f"[Figure on page {page_num}] "
                        f"Image extracted from the document. "
                        f"Path: {image_path}"
                    )
                if ocr_text:
                    base_description += f"\nOCR Text: {ocr_text}"

                img_elem.content = base_description
                img_elem.element_type = "figure"

                # Store LaTeX in a custom attribute so the chunker can pick it up
                if latex_result.get("latex"):
                    img_elem._latex_source = latex_result["latex"]
                else:
                    img_elem._latex_source = None

                processed_elements.append(img_elem)

            if not processed_elements:
                logger.warning(f"No content extracted from {original_filename}")
                doc.status = "failed"
                self.document_store.update_status(doc.id, "failed")
                return doc

            # Step 6: Chunk the content
            self.document_store.update_progress(doc.id, "Chunking content (step 4/6)")
            logger.info(f"Chunking {len(processed_elements)} multimodal elements...")
            chunks = self.chunker.chunk(processed_elements, original_filename)

            if not chunks:
                logger.warning(f"No chunks created for {original_filename}")
                doc.status = "failed"
                self.document_store.update_status(doc.id, "failed")
                return doc

            # Step 7: Generate embeddings
            self.document_store.update_progress(doc.id, "Generating embeddings (step 5/6)")
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            texts = [chunk.content for chunk in chunks]
            embeddings = self.embedding_service.embed_texts(texts)

            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding

            # Step 8: Store in vector database
            self.document_store.update_progress(doc.id, "Storing in vector database (step 6/6)")
            logger.info("Storing chunks in vector database...")
            num_stored = self.vector_store.add_chunks(chunks)
            doc.total_chunks = num_stored

            # Step 9: Update document status
            doc.status = "completed"
            self.document_store.update_status(doc.id, "completed", num_stored, doc.total_pages)
            self.document_store.update_progress(doc.id, "")

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

        # Fix 5: delete from SQLite first so the record is gone even if the
        # ChromaDB or file-system deletion fails partway through.
        self.document_store.delete_document(doc_id)

        # Delete file from disk
        if os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except OSError as e:
                logger.warning(f"Could not remove file {doc.file_path}: {e}")

        # Delete chunks from vector store last
        try:
            self.vector_store.delete_by_source(doc.filename)
        except Exception as e:
            logger.warning(f"Could not remove vector chunks for {doc.filename}: {e}")

        logger.info(f"Deleted document: {doc.filename} ({doc_id})")
        return True

    def get_all_documents(self) -> list[DocumentInfo]:
        """Get all ingested documents."""
        return self.document_store.get_all_documents()
