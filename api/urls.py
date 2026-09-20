from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    RegisterView,
    DocumentUploadView,
    StudyMaterialListView,
    StudyMaterialDeleteView,
    ChatView,
)

urlpatterns = [
    # Auth
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Document management
    path('upload-pdf/', DocumentUploadView.as_view(), name='upload_pdf'),
    path('get-materials/', StudyMaterialListView.as_view(), name='get_materials'),
    path('delete-material/<int:pk>/', StudyMaterialDeleteView.as_view(), name='delete_material'),

    # RAG Chat
    path('chat/', ChatView.as_view(), name='chat'),
]