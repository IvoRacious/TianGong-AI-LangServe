import datetime
from typing import Optional

from openai import OpenAI
from pinecone import Pinecone
from supabase import Client, create_client
# from xata.client import XataClient

from src.config.config import (
    OPENAI_API_KEY,
    OPENAI_EMBEDDING_MODEL_V3,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_NAMESPACE_SCI,
    SUPABASE_KB_KEY,
    SUPABASE_KB_URL,
    # XATA_API_KEY,
    # XATA_DOCS_DB_URL,
)


async def search(
    query: str,
    top_k: Optional[int] = 16,
) -> list:
    """Semantic search in academic vector database."""

    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    pc = Pinecone(api_key=PINECONE_API_KEY)
    idx = pc.Index(PINECONE_INDEX_NAME)

    supabase: Client = create_client(SUPABASE_KB_URL, SUPABASE_KB_KEY)

    # xata = XataClient(api_key=XATA_API_KEY, db_url=XATA_DOCS_DB_URL)

    response = openai_client.embeddings.create(
        input=query, model=OPENAI_EMBEDDING_MODEL_V3
    )
    query_vector = response.data[0].embedding

    docs = idx.query(
        namespace=PINECONE_NAMESPACE_SCI,
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
    )

    doi_set = set()
    for matche in docs["matches"]:
        doi = matche["id"].rpartition("_")[0]
        doi_set.add(doi)

    supabase_response = (
        supabase.table("journals").select("doi,title,authors").in_("doi", list(doi_set)).execute()
    )
    records = supabase_response.data

    # xata_response = xata.data().query(
    #     "journals",
    #     {
    #         "columns": ["doi", "title", "authors"],
    #         "filter": {
    #             "doi": {"$any": list(doi_set)},
    #         },
    #     },
    # )

    # records = xata_response.get("records", [])
    records_dict = {record["doi"]: record for record in records}

    docs_list = []
    for doc in docs["matches"]:
        doi = doc["id"].rpartition("_")[0]
        record = records_dict.get(doi, {})

        if record:
            date = datetime.datetime.fromtimestamp(doc.metadata["date"])
            formatted_date = date.strftime("%Y-%m")
            authors = ", ".join(record["authors"])
            url = "https://doi.org/{}".format(doi)

            source_entry = "[{}. {}. {}. {}.]({})".format(
                record["title"],
                doc.metadata["journal"],
                authors,
                formatted_date,
                url,
            )
            docs_list.append({"content": doc.metadata["text"], "source": source_entry})

    return docs_list
