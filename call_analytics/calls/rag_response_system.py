import os
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain_groq import ChatGroq
from langchain_core.documents import Document

# === Step 1: Load PDF Knowledge Base ===
PDF_DIR = "calls/pdf_docs/"
VECTOR_DIR = "calls/vector_db/"

def load_and_split_pdfs():
    all_text = ""
    for filename in os.listdir(PDF_DIR):
        if filename.endswith(".pdf"):
            path = os.path.join(PDF_DIR, filename)
            try:
                with fitz.open(path) as doc:
                    print(f"Reading {filename}...")
                    for page in doc:
                        all_text += page.get_text()
            except Exception as e:
                print(f"⚠️ Failed to load {filename}: {e}")


    if not all_text.strip():
        raise ValueError("📄 No extractable text found in any PDF in calls/pdf_docs/")

    # Now split
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    return [Document(page_content=chunk) for chunk in text_splitter.split_text(all_text)]


# === Step 2: Create or Load Vector Store ===
def get_vector_store():
    if os.path.exists(VECTOR_DIR):
        return FAISS.load_local(VECTOR_DIR, HuggingFaceEmbeddings(), allow_dangerous_deserialization=True)
    docs = load_and_split_pdfs()
    if not docs:
        raise ValueError("No chunks generated from PDFs – cannot build vector DB.")

    vectorstore = FAISS.from_documents(docs, HuggingFaceEmbeddings())
    vectorstore.save_local(VECTOR_DIR)
    return vectorstore

# === Step 3: Run RAG-Powered Response ===
def generate_rag_response(user_input):
    vectorstore = get_vector_store()
    retriever = vectorstore.as_retriever(search_type="similarity", k=5)

    groq_llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama3-8b-8192"
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=groq_llm,
        retriever=retriever,
        return_source_documents=True,
        chain_type="stuff"
    )

    response = qa_chain.invoke(user_input)
    return {
        "answer": response["result"],
        "sources": [doc.metadata.get("source", "N/A") for doc in response["source_documents"]]
    }
