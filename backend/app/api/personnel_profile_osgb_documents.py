"""Route-order guard for OSGB professional documents.

The exact document paths are isolated under /osgb-personnel-profiles and are
registered before the generic OSGB profile routes.
"""
from fastapi import APIRouter

from app.api.personnel_profile_osgb import (
    archive_osgb_document,
    download_osgb_document,
    get_osgb_document_versions,
    get_osgb_documents,
    upload_osgb_document,
)

router = APIRouter(prefix="/osgb-personnel-profiles", tags=["OSGB Dijital Profesyonel Kartı Belgeleri"])
router.add_api_route(
    "/{profile_id}/documents/upload",
    upload_osgb_document,
    methods=["POST"],
)
router.add_api_route(
    "/{profile_id}/documents",
    get_osgb_documents,
    methods=["GET"],
)
router.add_api_route(
    "/{profile_id}/documents/{document_key}/versions",
    get_osgb_document_versions,
    methods=["GET"],
)
router.add_api_route(
    "/{profile_id}/documents/{document_key}/archive",
    archive_osgb_document,
    methods=["POST"],
)
router.add_api_route(
    "/{profile_id}/document-versions/{document_id}/download",
    download_osgb_document,
    methods=["GET"],
)
