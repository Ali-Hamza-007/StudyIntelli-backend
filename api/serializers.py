from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Document, StudyMaterial


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        return user


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = ('user', 'extracted_text')


class StudyMaterialSerializer(serializers.ModelSerializer):
    """
    Used for CREATE responses (upload) — returns the document FK as an integer.
    The upload view manually combines this with DocumentSerializer output to
    produce the full nested response.
    """
    class Meta:
        model = StudyMaterial
        fields = '__all__'
        read_only_fields = ('user', 'document')


class StudyMaterialDetailSerializer(serializers.ModelSerializer):
    """
    Used for LIST / GET responses — nests the full Document object so Flutter
    can read document.file, document.title, etc. without a second request.

    Fix for Bug #3: previously StudyMaterialListView used StudyMaterialSerializer
    which returned `document` as an integer FK, causing Flutter to fail when it
    tried to read material['document']['file'].
    """
    document = DocumentSerializer(read_only=True)

    class Meta:
        model = StudyMaterial
        fields = '__all__'
        read_only_fields = ('user', 'document')
