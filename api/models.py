from django.db import models
from django.contrib.auth.models import User


class Document(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    extracted_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class StudyMaterial(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_materials')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='materials')
    important_questions = models.JSONField(default=list)
    mcqs = models.JSONField(default=list)
    fill_in_the_blanks = models.JSONField(default=list)
    short_questions = models.JSONField(default=list)
    long_questions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Materials for {self.document.title}"


class DocumentChunk(models.Model):
    """
    Stores a single text chunk and its embedding vector for RAG retrieval.
    One document → many chunks.  Chunks are ordered by chunk_index.
    The embedding field stores a JSON list of floats produced by
    sentence-transformers (or the BOW fallback).
    """
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='chunks',
    )
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    # Stored as a JSON array of floats — no extra vector-DB dependency needed.
    embedding = models.JSONField(default=list)

    class Meta:
        ordering = ['chunk_index']
        unique_together = [('document', 'chunk_index')]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"
