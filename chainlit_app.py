import os
import re
import chainlit as cl
from dotenv import load_dotenv 
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

load_dotenv()

DISCLAIMER_TEXT = """
**⚠️ LEGAL & DATA DISCLAIMER (READ BEFORE USE)**

This tool is a **prototype** for **educational and research** purposes only, built as a developer demo. It provides a **high-level, non-authoritative** summary and does **not** provide legal advice.

**Not legal advice:** The output is not a substitute for advice from a qualified legal professional.
**Accuracy limits:** The analysis may be incomplete, outdated, or incorrect. Always verify against the **official EU AI Act text** and related guidance.
**No reliance:** Do not use this tool as the sole basis for compliance decisions, audits, or legal conclusions.

**Age requirement (important):**
- This tool is **not intended for users under 18**. By using it, you confirm that you are **18+**.
- Reference: [Gemini API Additional Terms (Age requirements)](https://ai.google.dev/gemini-api/terms)

**Data & privacy (important):**
- **Do not paste personal data or confidential information** (names, emails, phone numbers, IDs, CVs, health data, contracts, internal company details).
- Your input is sent to **Google Gemini API** for processing.
- This app does **not intentionally store** your input or the generated output.
- This app uses a **billing-enabled (paid tier)** Gemini API setup. According to Google’s paid tier documentation, prompts and responses **aren’t used to improve Google products**.
  - [Gemini API billing documentation](https://ai.google.dev/gemini-api/docs/billing)
  - [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)

**Limitation of liability:** To the maximum extent permitted by law, the developer is not liable for damages or losses resulting from use of this prototype.

*By clicking "I Agree & Continue" below, you confirm you have read, understood, and accepted these terms.*
"""

async def initialize_ai_system(msg_element):
    """Loads the Vector DB and LLM into the user session."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        vectorstore = Chroma(
            persist_directory="./chroma_db",
            embedding_function=embeddings
        )

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite", 
            temperature=0.3,
            google_api_key=api_key
        )

        system_prompt = (
            "You are a Senior Legal Compliance Officer specializing in the EU AI Act. "
            "Use the following pieces of retrieved context to determine the risk level of the user's AI system."
            "If the user writes about an unrelated topic to just chat, respond with 'This tool only assesses AI systems under the EU AI Act.'\n\n"
            "If user asks you to respond in another language. Do it.'\n\n"
            "If you don't know the answer, say that you don't know.\n\n"

            "TASK:\n"
            "Given the user's AI system description, determine the most likely EU AI Act risk bucket, in this order:\n"
            "A) Prohibited\n"
            "B) High Risk\n"
            "C) Limited Risk (transparency duties)\n"
            "D) Minimal Risk / Not clearly covered by the provided context\n"
            "After listing the risk levels, explain your reasoning.\n\n"

            "OUTPUT FORMAT:\n"
            "Start your answer with exactly this first line:\n"
            "Risk level (not legal advice): <Prohibited | High Risk | Limited Risk | Minimal/Unclear>\n\n"

            "CONTEXT:\n{context}"
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])

        cl.user_session.set("vectorstore", vectorstore)
        cl.user_session.set("llm", llm)
        cl.user_session.set("prompt", prompt)
        cl.user_session.set("is_authorized", True)

        msg_element.content = "✅ **System Ready.** Describe your AI system to generate a preliminary risk summary."
        await msg_element.update()

    except Exception as e:
        msg_element.content = f"❌ **System Error:** {str(e)}"
        await msg_element.update()


@cl.on_chat_start
async def on_chat_start():
    # A. Check for API Key first
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        await cl.Message(content="⚠️ **Error:** GOOGLE_API_KEY not found.").send()
        return

    # B. Show Title & Disclaimer
    welcome_message = f"""# ⚖️ EU AI Act RAG Screener Demo
#### Not legal advice: Prototype EU AI Act risk screening for AI systems with citations.

{DISCLAIMER_TEXT}
"""
    await cl.Message(content=welcome_message).send()

    # C. Ask for Action
    res = await cl.AskActionMessage(
        content="**Do you agree to the terms above?**",
        actions=[
            cl.Action(
                name="agree", 
                payload={"value": "agree"}, 
                label="✅ I am +18 and Agree & Continue"
            ),
            cl.Action(
                name="decline", 
                payload={"value": "decline"}, 
                label="❌ Decline"
            )
        ]
    ).send()

    # D. Handle Response
    if res and res.get("name") == "agree":
        msg = cl.Message(content="🧠 **Agreement Accepted.** Loading Legal Database...")
        await msg.send()
        
        await initialize_ai_system(msg)
        
    else:
        await cl.Message(content="⛔ **Access Denied.** You must agree to the terms to use this tool. Please refresh the page to start over.").send()
        cl.user_session.set("is_authorized", False)


def extract_legal_ref(text):
    match = re.search(r'(Article\s+\d+|Annex\s+[IVX]+)', text, re.IGNORECASE)
    return match.group(1) if match else "Legal Text"


@cl.on_message
async def main(message: cl.Message):
    is_authorized = cl.user_session.get("is_authorized")
    if not is_authorized:
        await cl.Message(content="⛔ You must agree to the disclaimer to proceed. Please refresh.").send()
        return

    vectorstore = cl.user_session.get("vectorstore")
    llm = cl.user_session.get("llm")
    prompt = cl.user_session.get("prompt")

    if not vectorstore:
        await cl.Message(content="⚠️ System not initialized. Please refresh.").send()
        return

    msg = cl.Message(content="**⚠️ Draft assessment only. Not legal advice. The model can be wrong or overly certain. Verify against the cited EUR-Lex text and consult a qualified professional for decisions.**\n\n")
    await msg.send()
    
    docs = await cl.make_async(vectorstore.similarity_search)(message.content, k=5)
    context_text = "\n\n".join(doc.page_content for doc in docs)
    
    chain = prompt | llm
    
    async for chunk in chain.astream(
        {"input": message.content, "context": context_text},
        config=RunnableConfig(callbacks=[cl.LangchainCallbackHandler()])
    ):
        token = chunk.content
        if isinstance(token, list):
            token = "".join(token)
        if token: 
            await msg.stream_token(token)

    source_elements = []
    pdf_base_url = "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689"

    for i, doc in enumerate(docs, start=1):
        ref_label = extract_legal_ref(doc.page_content)
        raw_page = doc.metadata.get('page', 0)
        page_num = int(raw_page) + 1 if raw_page is not None else 1
        source_name = f"Source {i}: {ref_label} (Page {page_num})"
        full_link = f"{pdf_base_url}#page={page_num}"
        popup_content = f"**🔗 [Open Reference]({full_link})**\n\n{doc.page_content}"

        source_elements.append(
            cl.Text(name=source_name, content=popup_content, display="inline")
        )

    msg.elements = source_elements
    await msg.update()