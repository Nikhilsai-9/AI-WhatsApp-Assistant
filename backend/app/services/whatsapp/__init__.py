"""WhatsApp integration service package."""

from app.services.whatsapp.pipeline import WhatsAppPipeline, get_pipeline

__all__ = ["WhatsAppPipeline", "get_pipeline"]