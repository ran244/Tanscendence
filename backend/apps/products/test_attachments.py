from django.core.files.uploadedfile import SimpleUploadedFile

from apps.common.tests_base import BaseTestCase
from apps.products.models import Category, Product, ProductAttachment


class ProductAttachmentApiTests(BaseTestCase):
    def setUp(self):
        self.owner = self.create_user("attachment_owner")
        self.category = Category.objects.create(name="Attachment test")
        self.product = Product.objects.create(owner=self.owner, name="Documented lot", category=self.category)
        self.csrf = self.api_login(self.owner)

    def test_upload_download_and_delete_pdf(self):
        upload = SimpleUploadedFile("proof.pdf", b"%PDF-1.4\nproof", content_type="application/pdf")
        response = self.client.post(f"/api/products/{self.product.id}/attachments/", {"file": upload}, format="multipart", headers={"X-CSRFToken": self.csrf})
        self.assertEqual(response.status_code, 201, response.data)
        attachment_id = response.data["id"]
        self.assertTrue(ProductAttachment.objects.filter(pk=attachment_id).exists())

        download = self.client.get(f"/api/products/{self.product.id}/attachments/{attachment_id}/download/")
        self.assertEqual(download.status_code, 200)
        deleted = self.api_delete(f"/api/products/{self.product.id}/attachments/{attachment_id}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(ProductAttachment.objects.filter(pk=attachment_id).exists())

    def test_rejects_disguised_document(self):
        upload = SimpleUploadedFile("fake.pdf", b"not really a pdf", content_type="application/pdf")
        response = self.client.post(f"/api/products/{self.product.id}/attachments/", {"file": upload}, format="multipart", headers={"X-CSRFToken": self.csrf})
        self.assertEqual(response.status_code, 400)
