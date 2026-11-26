
import os
import time
import urllib.request
from pathlib import Path

import cloudinary
from cloudinary import api, uploader, utils
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class CloudinaryBaseStorage(Storage):
    delivery_type = "upload"

    def __init__(self):
        self.local_storage = FileSystemStorage(
            location=settings.MEDIA_ROOT,
            base_url=settings.MEDIA_URL
        )

    def cloudinary_enabled(self):
        return os.environ.get(
            "CLOUDINARY_STORAGE_ENABLED", "false"
        ).lower() == "true"

    def configure_cloudinary(self):
        cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
        api_key = os.environ.get("CLOUDINARY_API_KEY")
        api_secret = os.environ.get("CLOUDINARY_API_SECRET")

        if not all([cloud_name, api_key, api_secret]):
            raise ImproperlyConfigured(
                "Cloudinary environment variables are incomplete."
            )

        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )

    def parse_name(self, name):
        if not name.startswith("cloudinary/"):
            return None

        stored_path = name[len("cloudinary/"):]
        public_id, separator, file_format = stored_path.rpartition(".")

        if not separator or not public_id or not file_format:
            raise ValueError("Invalid Cloudinary storage filename.")

        return public_id, file_format

    def _save(self, name, content):
        if not self.cloudinary_enabled():
            return self.local_storage._save(name, content)

        self.configure_cloudinary()

        folder = str(Path(name).parent).replace("\\", "/")
        original_name = Path(name).stem

        if folder == ".":
            folder = ""

        if hasattr(content, "seek"):
            content.seek(0)

        result = uploader.upload(
            content,
            resource_type="image",
            type=self.delivery_type,
            folder=folder,
            public_id=original_name,
            unique_filename=True,
            overwrite=False
        )

        public_id = result["public_id"]
        file_format = result.get("format")

        if not file_format:
            raise ValueError("Cloudinary did not return a file format.")

        return f"cloudinary/{public_id}.{file_format}"

    def _open(self, name, mode="rb"):
        parsed = self.parse_name(name)

        if parsed is None:
            return self.local_storage.open(name, mode)

        return ContentFile(self.download_file(name))

    def download_file(self, name):
        url = self.url(name)

        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()

    def delete(self, name):
        parsed = self.parse_name(name)

        if parsed is None:
            return self.local_storage.delete(name)

        self.configure_cloudinary()
        public_id, file_format = parsed

        uploader.destroy(
            public_id,
            resource_type="image",
            type=self.delivery_type,
            invalidate=True
        )

    def exists(self, name):
        parsed = self.parse_name(name)

        if parsed is None:
            return self.local_storage.exists(name)

        self.configure_cloudinary()
        public_id, file_format = parsed

        try:
            api.resource(
                public_id,
                resource_type="image",
                type=self.delivery_type
            )
            return True
        except Exception as error:
            if getattr(error, "http_code", None) == 404:
                return False
            raise

    def size(self, name):
        parsed = self.parse_name(name)

        if parsed is None:
            return self.local_storage.size(name)

        self.configure_cloudinary()
        public_id, file_format = parsed

        result = api.resource(
            public_id,
            resource_type="image",
            type=self.delivery_type
        )

        return result["bytes"]

    def listdir(self, path):
        return self.local_storage.listdir(path)

    def url(self, name):
        parsed = self.parse_name(name)

        if parsed is None:
            return self.local_storage.url(name)

        self.configure_cloudinary()
        public_id, file_format = parsed

        if self.delivery_type == "authenticated":
            return utils.private_download_url(
                public_id,
                file_format,
                resource_type="image",
                type="authenticated",
                expires_at=int(time.time()) + 900,
                attachment=False,
                secure=True
            )

        return utils.cloudinary_url(
            public_id,
            format=file_format,
            resource_type="image",
            type="upload",
            secure=True
        )[0]


@deconstructible
class CloudinaryProfilePictureStorage(CloudinaryBaseStorage):
    delivery_type = "upload"


@deconstructible
class CloudinaryEvidenceStorage(CloudinaryBaseStorage):
    delivery_type = "authenticated"
