import logging

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from django.contrib.auth.models import User

from .models import Document, StudyMaterial
from .serializers import (
    UserSerializer,
    DocumentSerializer,
    StudyMaterialSerializer,
    StudyMaterialDetailSerializer,
)
from .services.pdf_service import PDFExtractionService
from .services.llm_service import LLMService
from .services.rag_service import RAGService

logger = logging.getLogger(__name__)


# ─── Auth ───────────────────────────────────────────────────────────────────

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = UserSerializer


# ─── Document Upload ─────────────────────────────────────────────────────────

class DocumentUploadView(generics.CreateAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        document = serializer.save(user=request.user)

        try:
            # 1. Extract raw text from the PDF
            text = PDFExtractionService.extract_text(document.file)
            document.extracted_text = text
            document.save()

            # 2. Generate study questions via Groq (LLM chunking)
            llm_service = LLMService()
            materials_json = llm_service.get_study_materials(text)

            material = StudyMaterial.objects.create(
                user=request.user,
                document=document,
                important_questions=materials_json.get('important_questions', []),
                mcqs=materials_json.get('mcqs', []),
                fill_in_the_blanks=materials_json.get('fill_in_the_blanks', []),
                short_questions=materials_json.get('short_questions', []),
                long_questions=materials_json.get('long_questions', []),
            )

            # 3. Build the RAG index (embeddings) for the chat feature
            rag_service = RAGService()
            try:
                chunk_count = rag_service.build_index(document)
                logger.info(f"RAG index built: {chunk_count} chunks for document {document.id}")
            except Exception as rag_err:
                # RAG index failure is non-fatal — questions are already saved
                logger.error(f"RAG index build failed for document {document.id}: {rag_err}", exc_info=True)

            # Return the full upload response with both document and material
            # The Flutter app stores the whole object, so both keys must be present.
            document_serializer = DocumentSerializer(document, context={'request': request})
            material_serializer = StudyMaterialSerializer(material)

            return Response({
                'document': document_serializer.data,
                'materials': material_serializer.data,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error processing document {document.id}: {e}", exc_info=True)
            document.delete()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─── Study Material List ─────────────────────────────────────────────────────

class StudyMaterialListView(generics.ListAPIView):
    """
    Returns all study materials for the authenticated user, with the full
    nested Document object included (fix for Bug #3 — previously returned
    document as an integer FK which broke the Flutter UI).
    """
    serializer_class = StudyMaterialDetailSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return (
            StudyMaterial.objects
            .filter(user=self.request.user)
            .select_related('document')   # Avoids N+1 queries
            .order_by('-created_at')
        )


# ─── Study Material Delete ───────────────────────────────────────────────────

class StudyMaterialDeleteView(generics.DestroyAPIView):
    serializer_class = StudyMaterialDetailSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return StudyMaterial.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        document = instance.document

        # Safety check: only touch the document if it truly belongs to this user.
        if document.user_id != self.request.user.id:
            instance.delete()
            return

        # Remove the physical file from storage before deleting the DB row.
        if document.file:
            document.file.delete(save=False)

        # Deleting the Document cascades: removes StudyMaterial + DocumentChunks.
        document.delete()


# ─── RAG Chat ────────────────────────────────────────────────────────────────

class ChatView(APIView):
    """
    POST /api/chat/
    Body: {"document_id": <int>, "question": "<string>"}
    Returns: {"answer": "<string>"}

    Retrieves the top-k most relevant chunks from the document's RAG index
    and uses Groq to generate a contextual answer.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        document_id = request.data.get('document_id')
        question = request.data.get('question', '').strip()

        if not document_id:
            return Response(
                {'error': 'document_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not question:
            return Response(
                {'error': 'question is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify the document belongs to the requesting user
        try:
            document = Document.objects.get(id=document_id, user=request.user)
        except Document.DoesNotExist:
            return Response(
                {'error': 'Document not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        rag_service = RAGService()
        try:
            answer = rag_service.query(document, question)
            return Response({'answer': answer}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Chat query error: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to generate answer. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )