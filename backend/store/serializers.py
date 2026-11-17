from rest_framework import serializers
from .models import Product
from django.conf import settings


class ProductSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        if not obj.image:
            return None

        name = str(obj.image)  # e.g. "products/bi8lcz0ijwraapmkhzuf"

        # If it's already a full URL, return as-is
        if name.startswith('http'):
            return name

        # Build full Cloudinary URL from the public_id
        cloud_name = settings.CLOUDINARY_STORAGE.get('CLOUD_NAME')
        return f"https://res.cloudinary.com/{cloud_name}/image/upload/{name}"

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'price',
            'description',
            'category',
            'stock',
            'created_at',
            'image_url',
        ]

