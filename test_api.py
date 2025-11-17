#!/usr/bin/env python3
"""
Test script for Finance RAG API
Tests document upload and RAG chat functionality
"""

import csv
import json
import os
import sys
from pathlib import Path

import httpx  # type: ignore

# API base URL - set via environment variable API_URL or change default
# Example: export API_URL=http://your-hosted-api.com
API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")
API_PREFIX = f"{API_BASE_URL}/api/v1"
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
DOCUMENT_COLLECTION = os.getenv("QDRANT_DOCUMENT_COLLECTION", "document_chunks")
KB_COLLECTION = os.getenv("QDRANT_KB_COLLECTION", "knowledge_base_chunks")

print(f"🌐 Testing API at: {API_BASE_URL}")
print(f"📡 API Prefix: {API_PREFIX}\n")

# Test files
TEST_FILES_DIR = Path(__file__).parent / "test_files"
PDF_FILE = TEST_FILES_DIR / "strafi_2024.pdf"
DOCX_FILE = TEST_FILES_DIR / "9115.docx"
KB_CSV_PATH = Path(__file__).parent / "knowledge_base" / "train_data.csv"


def print_response(title: str, response: httpx.Response):
    """Print formatted response"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
    except:
        print(f"Response: {response.text[:500]}")
    print()


def build_kb_question() -> str:
    if not KB_CSV_PATH.exists():
        return "Расскажи кратко о политике компании по работе с внутренними документами из базы знаний."
    with KB_CSV_PATH.open("r", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            title = (row.get("annotation") or "").strip()
            source_id = (row.get("id") or "kb").strip()
            if title:
                return f"Суммируй основные положения материала «{title}» (источник {source_id}) из внутренней базы знаний."
    return "Расскажи кратко о политике компании по работе с внутренними документами из базы знаний."


async def reset_document_vectors(client: httpx.AsyncClient) -> None:
    if not QDRANT_URL:
        print("⚠️  QDRANT_URL is not set; skipping vector reset.")
        return
    endpoint = f"{QDRANT_URL}/collections/{DOCUMENT_COLLECTION}"
    print(f"🧹 Dropping Qdrant collection '{DOCUMENT_COLLECTION}' at {endpoint} ...")
    try:
        response = await client.delete(endpoint, timeout=30.0)
        if response.status_code in (200, 202, 204):
            print("✅ Document collection dropped (will be recreated on next upload).")
        elif response.status_code == 404:
            print("ℹ️  Document collection did not exist; nothing to drop.")
        else:
            print(f"⚠️  Failed to drop collection: {response.status_code} {response.text[:200]}")
    except Exception as exc:
        print(f"⚠️  Could not contact Qdrant at {endpoint}: {exc}")


async def purge_user_documents(client: httpx.AsyncClient, headers: dict[str, str]) -> None:
    print("🧽 Purging existing user documents...")
    try:
        docs_response = await client.get(f"{API_PREFIX}/document", headers=headers)
        if docs_response.status_code != 200:
            print(f"⚠️  Cannot list documents: {docs_response.status_code}")
            return
        docs = docs_response.json()
        if not docs:
            print("ℹ️  No documents to delete.")
            return
        for doc in docs:
            doc_id = doc.get("document_id")
            if not doc_id:
                continue
            delete_resp = await client.delete(
                f"{API_PREFIX}/document/{doc_id}", headers=headers
            )
            status = "✅" if delete_resp.status_code in (200, 204) else "⚠️"
            print(f"{status} Deleted document {doc_id} (status {delete_resp.status_code})")
    except Exception as exc:
        print(f"⚠️  Failed to purge documents: {exc}")


async def test_api():
    """Run API tests"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Check API health first
        print("🏥 Checking API health...")
        try:
            health_response = await client.get(f"{API_BASE_URL}/health")
            if health_response.status_code == 200:
                print(f"✅ API is healthy: {health_response.json()}\n")
            else:
                print(f"⚠️  API health check returned: {health_response.status_code}\n")
        except Exception as e:
            print(f"❌ Cannot reach API at {API_BASE_URL}: {e}")
            print(f"   Please check if the API is running or set API_URL environment variable")
            print(f"   Example: export API_URL=http://your-api-host:8000")
            return
        # Step 1: Register a test user
        print("🔐 Step 1: Registering test user...")
        register_data = {
            "username": "test_user",
            "email": "test@example.com",
            "password": "testpassword123",
            "role": 0,  # Role.USER as IntEnum
        }
        register_response = await client.post(
            f"{API_PREFIX}/auth/register",
            json=register_data
        )
        print_response("Register User", register_response)
        
        if register_response.status_code not in [200, 201, 400, 409]:
            print("❌ Registration failed!")
            return
        
        # Step 2: Login to get token
        print("🔑 Step 2: Logging in...")
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }
        login_response = await client.post(
            f"{API_PREFIX}/auth/login",
            json=login_data  # Using JSON for login
        )
        print_response("Login", login_response)
        
        if login_response.status_code != 200:
            print("❌ Login failed!")
            return
        
        token_data = login_response.json()
        token = token_data.get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Reset Qdrant document vectors
        await reset_document_vectors(client)

        # Remove existing docs from user account before uploading new ones
        await purge_user_documents(client, headers)
        
        # Step 3: Upload PDF document
        print("📄 Step 3: Uploading PDF document...")
        if PDF_FILE.exists():
            with open(PDF_FILE, "rb") as f:
                files = {"file": (PDF_FILE.name, f, "application/pdf")}
                upload_response = await client.post(
                    f"{API_PREFIX}/document",
                    headers=headers,
                    files=files
                )
            print_response("Upload PDF", upload_response)
            
            if upload_response.status_code == 200:
                pdf_doc = upload_response.json()
                pdf_doc_id = pdf_doc.get("document_id")
                print(f"✅ PDF uploaded with ID: {pdf_doc_id}")
            else:
                pdf_doc_id = None
                print("❌ PDF upload failed!")
        else:
            print(f"⚠️  PDF file not found: {PDF_FILE}")
            pdf_doc_id = None
        
        # Step 4: Upload DOCX document
        print("📄 Step 4: Uploading DOCX document...")
        if DOCX_FILE.exists():
            with open(DOCX_FILE, "rb") as f:
                files = {"file": (DOCX_FILE.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
                upload_response = await client.post(
                    f"{API_PREFIX}/document",
                    headers=headers,
                    files=files
                )
            print_response("Upload DOCX", upload_response)
            
            if upload_response.status_code == 200:
                docx_doc = upload_response.json()
                docx_doc_id = docx_doc.get("document_id")
                print(f"✅ DOCX uploaded with ID: {docx_doc_id}")
            else:
                docx_doc_id = None
                print("❌ DOCX upload failed!")
        else:
            print(f"⚠️  DOCX file not found: {DOCX_FILE}")
            docx_doc_id = None
        
        # Step 5: List documents
        print("📋 Step 5: Listing all documents...")
        docs_response = await client.get(
            f"{API_PREFIX}/document",
            headers=headers
        )
        print_response("List Documents", docs_response)
        
        # Step 6: Get a prompt ID (we need this to create a chat)
        # For now, let's try to create a chat with prompt_id=1
        # If that fails, we'll handle it
        print("💬 Step 6: Creating a chat...")
        chat_data = {"prompt_id": 1}  # Assuming prompt_id=1 exists
        chat_response = await client.post(
            f"{API_PREFIX}/chat",
            headers=headers,
            json=chat_data
        )
        print_response("Create Chat", chat_response)
        
        if chat_response.status_code == 201:
            chat_info = chat_response.json()
            chat_id = chat_info.get("chat_id")
            print(f"✅ Chat created with ID: {chat_id}")
        else:
            # Try to get existing chats
            print("⚠️  Chat creation failed, trying to get existing chats...")
            chats_response = await client.get(
                f"{API_PREFIX}/chat",
                headers=headers
            )
            print_response("Get Chats", chats_response)
            
            if chats_response.status_code == 200:
                chats = chats_response.json()
                if chats:
                    chat_id = chats[0].get("chat_id")
                    print(f"✅ Using existing chat ID: {chat_id}")
                else:
                    print("❌ No chats available. Cannot test RAG.")
                    return
            else:
                print("❌ Cannot get chats. Cannot test RAG.")
                return
        
        async def send_message(title: str, content: str, documents: list[int] | None):
            payload = {"content": content, "documents_ids": documents or []}
            response = await client.post(
                f"{API_PREFIX}/chat/{chat_id}/message", headers=headers, json=payload
            )
            print(f"\n{'='*60}")
            print(title)
            print(f"{'='*60}")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print(response.text)

        print("🤖 Step 7: Testing RAG - General question (no documents)...")
        await send_message(
            "RAG Response (General Question)",
            "Привет! Расскажи о себе и своих возможностях.",
            [],
        )

        if pdf_doc_id or docx_doc_id:
            print("\n🤖 Step 8: Testing RAG - Document-specific question...")
            selected_docs = [doc_id for doc_id in [pdf_doc_id, docx_doc_id] if doc_id]
            await send_message(
                "RAG Response (Document Question)",
                "Что содержится в этих документах? Кратко опиши основную информацию.",
                selected_docs,
            )

        print("\n🔍 Step 9: Testing RAG - Search for documents...")
        await send_message(
            "RAG Response (Search Query)",
            "Найди документы, связанные со штрафами и наказаниями",
            [],
        )

        kb_question = build_kb_question()
        print("\n📚 Step 10: Testing knowledge-base fallback...")
        await send_message(
            "RAG Response (KB Question)",
            kb_question,
            [],
        )

        print("\n❓ Step 11: Testing clarification flow...")
        await send_message(
            "RAG Response (Clarification)",
            "Сделай что-нибудь полезное",
            [],
        )

        print("\n🏦 Step 12: Testing CBR data tool...")
        await send_message(
            "RAG Response (CBR key rate)",
            "Подскажи текущую ключевую ставку ЦБ РФ и дату её установления.",
            [],
        )

        print("\n📰 Step 13: Testing Tavily finance news tool...")
        await send_message(
            "RAG Response (Finance News)",
            "Расскажи последние финансовые новости о ключевой ставке ЦБ РФ за последние недели.",
            [],
        )
        
        print("\n" + "=" * 60)
        print("✅ Testing completed!")
        print("=" * 60)


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(test_api())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

