import os
import getpass
import time
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

# 1. Setup API Key
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter your Google API Key: ")

def ingest_docs():
    print("🚀 Starting Ingestion (Slow Mode)...")

    # 2. Load PDF
    pdf_path = "data/eu_ai_act.pdf"
    if not os.path.exists(pdf_path):
        print("❌ Error: PDF not found.")
        return

    loader = PyMuPDFLoader(pdf_path)
    docs = loader.load()
    print(f"✅ Loaded {len(docs)} pages.")

    # 3. Optimize Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=4000,  # DOUBLED size to halve the number of requests
        chunk_overlap=500,
        separators=["\n\n", "\n", " ", ""]
    )
    splits = text_splitter.split_documents(docs)
    print(f"🔪 Optimized into {len(splits)} chunks (Less API usage).")

    # 4. Initialize Database
    print("💾 Initializing ChromaDB with 'text-embedding-004'...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    
    vectorstore = Chroma(
        embedding_function=embeddings,
        persist_directory="./chroma_db"
    )

    # 5. Slow Ingestion Loop
    total_splits = len(splits)
    
    print(f"⏳ Processing {total_splits} chunks one-by-one...")

    for i, doc in enumerate(splits):
        try:
            vectorstore.add_documents([doc])
            
            print(f"   ✅ Chunk {i+1}/{total_splits} indexed.", end="\r")
            
            time.sleep(2) 
            
        except Exception as e:
            print(f"\n   ❌ Error on chunk {i+1}: {e}")
            time.sleep(60)

    print("\n🎉 Success! All data indexed.")

if __name__ == "__main__":
    ingest_docs()